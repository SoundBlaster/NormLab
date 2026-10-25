import ParkingAttribution
import Parking

-- The human operator records reviewed findings. This is not a finding that
-- the selected participant performed/omitted an act or incurred liability.
namespace NormLabParkingRuntime

open NormLabRelations NormLabStateRelations NormLabEvents NormLabActionAttribution

structure Scope where
  draft : Nat
  revision : Nat
  assessment : Nat
  revisionDigest : Nat
  episode : Nat
  participant : Nat
  vehicle : Nat
  eventDate : Nat
  location : Nat
  timeInterval : Nat
  deriving DecidableEq

structure SourceStatement where
  id : Nat
  episode : Nat
  confirmed : Bool
  deriving DecidableEq

structure Source where
  draft : Nat
  revision : Nat
  revisionDigest : Nat
  reviewed : Bool
  statements : List SourceStatement

structure FindingRow where
  condition : NormLabParking.Condition
  state : NormLabParking.Finding
  supports : List Nat
  deriving DecidableEq

structure Request where
  scope : Scope
  findings : List FindingRow
  claimedFine : Option Nat

-- Explicit operator decisions may come from outside the quoted text. Their
-- absence of citations is recorded, never promoted into source-backed evidence.
def uncitedConditions (request : Request) : List NormLabParking.Condition :=
  request.findings.filterMap fun row => match row.state with
    | .established | .refuted | .conflict =>
      if row.supports.isEmpty then some row.condition else none
    | _ => none

-- Empty strings encode to 1; all other UTF-16 strings have a larger token.
-- These coordinates are uninterpreted identities, not parsed dates/durations.
def normInput (request : Request) : NormLabParking.Input where
  finding condition :=
    ((request.findings.find? fun row => row.condition == condition).map (·.state)).getD .unreviewed
  present coordinate := match coordinate with
    | .vehicle => request.scope.vehicle != 1
    | .participant => request.scope.participant != 1
    | .eventDate => request.scope.eventDate != 1
    | .location => request.scope.location != 1
    | .timeInterval => request.scope.timeInterval != 1
  claimedFine := request.claimedFine

def bindingValid (source : Source) (request : Request) : Bool :=
  decide (source.draft = request.scope.draft) &&
  decide (source.revision = request.scope.revision) &&
  decide (source.revisionDigest = request.scope.revisionDigest) && source.reviewed &&
  decide (source.statements.map (·.id)).Nodup &&
  decide (request.findings.map (·.condition) = NormLabParking.conditions) &&
  request.findings.all fun row =>
    decide row.supports.Nodup && row.supports.all fun id =>
      source.statements.any fun statement =>
        statement.id == id && statement.episode == request.scope.episode && statement.confirmed

inductive EntityId where
  | operator | participant (id : Nat) | vehicle (id : Nat)
  deriving DecidableEq
inductive ActionId where
  | recordReviewedFindings
  deriving DecidableEq
inductive Fact where
  | scope (value : Scope)
  | finding (condition : NormLabParking.Condition) (state : NormLabParking.Finding)
  | support (condition : NormLabParking.Condition) (statement : Nat)
  deriving DecidableEq

def model : NormLabActionAttribution.Universe :=
  {Entity := EntityId, Episode := Nat, Action := ActionId,
    IsHuman := fun entity => entity = EntityId.operator}

instance : DecidableEq (Profile.signature model).Predicate :=
  inferInstanceAs (DecidableEq Profile.Predicate)
instance : ∀ sort, DecidableEq ((Profile.signature model).Entity sort) := by
  intro sort
  cases sort with
  | human => exact inferInstanceAs (DecidableEq {e : EntityId // e = EntityId.operator})
  | entity => exact inferInstanceAs (DecidableEq EntityId)
  | instrument => exact inferInstanceAs (DecidableEq (Option EntityId))
  | episode => exact inferInstanceAs (DecidableEq Nat)
  | action => exact inferInstanceAs (DecidableEq ActionId)
  | time | eventId | interpretationId => exact inferInstanceAs (DecidableEq Nat)

def snapshot (request : Request) : FiniteState Fact :=
  FiniteState.ofList (.scope request.scope :: request.findings.flatMap fun row =>
    .finding row.condition row.state :: row.supports.map (.support row.condition))

def event (request : Request) : RecordedEvent model.toUniverse Fact :=
  {key := ⟨request.scope.assessment, request.scope.episode, .recordReviewedFindings, 0, 1⟩,
    before := FiniteState.empty, after := snapshot request, ordered := by change (0 : Nat) ≤ 1; decide}

def registry (request : Request) : EventRegistry model.toUniverse Fact :=
  EventRegistry.ofList [event request] (by simp)

def registered (request : Request) : RegisteredEvent (registry request) :=
  ⟨event request, EventRegistry.ofList_lookup _ _ _ (by simp)⟩

def interpretation (request : Request) : Interpretation (registered request).record :=
  ⟨⟨request.scope.revision, .operator, .participant request.scope.participant,
    some (.vehicle request.scope.vehicle)⟩⟩

def context (request : Request) : HumanContext (u := model) (registry request) :=
  humanCandidate (registered request) (interpretation request) ⟨EntityId.operator, rfl⟩

-- The precondition is checked for the concrete runtime packet by the kernel.
-- The only profile grounds asserted here concern the operator's review action.
def input (source : Source) (request : Request) (_binding : bindingValid source request = true) :
    NormLabParkingAttribution.Input (u := model) (registry request) :=
  {event := registered request, interpretation := interpretation request,
    humanAnchor := ⟨EntityId.operator, rfl⟩, kind := .action,
    facts := Profile.grounds .action (context request).scope,
    catalog := [Profile.profileRule .action (context request).scope]}

def HasScope (request : Request) (result : GroundedTransition (u := model) (registry request)) : Prop :=
  result.context.scope.actor = EntityId.operator ∧
  result.context.scope.target = .participant request.scope.participant ∧
  result.context.scope.instrument = some (.vehicle request.scope.vehicle) ∧
  result.context.scope.episode = request.scope.episode ∧
  result.context.scope.eventId = request.scope.assessment ∧
  result.context.scope.interpretationId = request.scope.revision

theorem accepted_scope (source : Source) (request : Request) (binding : bindingValid source request = true)
    (result : GroundedTransition (u := model) (registry request))
    (accepted : NormLabParkingAttribution.propose (input source request binding) = some result) :
    HasScope request result := by
  rw [HasScope, NormLabParkingAttribution.accepted_context _ _ accepted]
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl⟩

theorem accepted_snapshot (source : Source) (request : Request) (binding : bindingValid source request = true)
    (result : GroundedTransition (u := model) (registry request))
    (accepted : NormLabParkingAttribution.propose (input source request binding) = some result) :
    result.context.event.record.after = snapshot request := by
  rw [NormLabParkingAttribution.accepted_record _ _ accepted]
  rfl

theorem source_identities (source : Source) (request : Request) (valid : bindingValid source request = true) :
    source.draft = request.scope.draft ∧ source.revision = request.scope.revision ∧
    source.revisionDigest = request.scope.revisionDigest ∧ source.reviewed = true := by
  simp only [bindingValid, Bool.and_eq_true, decide_eq_true_eq, and_assoc] at valid
  exact ⟨valid.1, valid.2.1, valid.2.2.1, valid.2.2.2.1⟩

theorem supports_scoped (source : Source) (request : Request) (valid : bindingValid source request = true)
    (row : FindingRow) (member : row ∈ request.findings) (id : Nat) (cited : id ∈ row.supports) :
    ∃ statement ∈ source.statements, statement.id = id ∧
      statement.episode = request.scope.episode ∧ statement.confirmed = true := by
  simp only [bindingValid, Bool.and_eq_true, decide_eq_true_eq, and_assoc] at valid
  have rowValid := (List.all_eq_true.mp valid.2.2.2.2.2.2) row member
  simp only [Bool.and_eq_true] at rowValid
  have referenceValid := (List.all_eq_true.mp rowValid.2) id cited
  rcases List.any_eq_true.mp referenceValid with ⟨statement, present, agreement⟩
  have agreement' : statement.id = id ∧ statement.episode = request.scope.episode ∧
      statement.confirmed = true := by
    simpa only [Bool.and_eq_true, beq_iff_eq, and_assoc] using agreement
  exact ⟨statement, present, agreement'⟩

end NormLabParkingRuntime
