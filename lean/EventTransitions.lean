import StateRelations

-- Supplied observations, role interpretations and bounded causal hypotheses.
-- No physical causality oracle or normative responsibility rule.
namespace NormLabEvents

open NormLabStateRelations

structure Universe where
  Entity : Type
  Episode : Type
  Action : Type

structure EventKey (u : Universe) where
  eventId : Nat
  episode : u.Episode
  action : u.Action
  start : Nat
  finish : Nat

structure RoleView (u : Universe) where
  interpretationId : Nat
  actor : u.Entity
  target : u.Entity
  instrument : Option u.Entity

-- Serializable scope only; not a record or proof of its existence.
structure Context (u : Universe) extends EventKey u, RoleView u

structure RecordedEvent (u : Universe) (Fact : Type) where
  key : EventKey u
  before : FiniteState Fact
  after : FiniteState Fact
  ordered : key.start ≤ key.finish

namespace RecordedEvent

variable {u : Universe} {Fact : Type} [DecidableEq Fact]

def consequence (event : RecordedEvent u Fact) : Delta Fact :=
  Delta.between event.before event.after

theorem roundtrip (event : RecordedEvent u Fact) :
    Delta.apply event.before event.consequence = event.after := Delta.roundtrip _ _

theorem added_iff (event : RecordedEvent u Fact) (fact : Fact) :
    fact ∈ event.consequence.added ↔ fact ∈ event.after ∧ fact ∉ event.before :=
  Delta.mem_added _ _ _

theorem removed_iff (event : RecordedEvent u Fact) (fact : Fact) :
    fact ∈ event.consequence.removed ↔ fact ∈ event.before ∧ fact ∉ event.after :=
  Delta.mem_removed _ _ _

end RecordedEvent

-- No state fields: every interpretation sees the same indexed record.
structure Interpretation {u : Universe} {Fact : Type} (event : RecordedEvent u Fact) where
  view : RoleView u

namespace Interpretation

variable {u : Universe} {Fact : Type} {event : RecordedEvent u Fact}

def context (interpretation : Interpretation event) : Context u := ⟨event.key, interpretation.view⟩
def before (_ : Interpretation event) := event.before
def after (_ : Interpretation event) := event.after
def consequence [DecidableEq Fact] (_ : Interpretation event) := event.consequence

theorem same_observations (a b : Interpretation event) :
    a.before = b.before ∧ a.after = b.after := ⟨rfl, rfl⟩

theorem same_consequence [DecidableEq Fact] (a b : Interpretation event) :
    a.consequence = b.consequence := rfl

@[simp] theorem context_key (a : Interpretation event) : a.context.toEventKey = event.key := rfl

end Interpretation

-- One immutable snapshot, not a global ID authority. Revised/disputed
-- observations require another record ID or an explicitly different snapshot.
structure EventRegistry (u : Universe) (Fact : Type) where
  lookup : Nat → Option (RecordedEvent u Fact)
  key_matches : ∀ id event, lookup id = some event → event.key.eventId = id

structure RegisteredEvent {u : Universe} {Fact : Type} (registry : EventRegistry u Fact) where
  record : RecordedEvent u Fact
  present : registry.lookup record.key.eventId = some record

namespace RegisteredEvent

variable {u : Universe} {Fact : Type} {registry : EventRegistry u Fact}

theorem same_id_same_record (a b : RegisteredEvent registry)
    (same : a.record.key.eventId = b.record.key.eventId) : a.record = b.record := by
  have equal := a.present
  rw [same, b.present] at equal
  exact (Option.some.inj equal).symm

theorem same_id_same_key (a b : RegisteredEvent registry)
    (same : a.record.key.eventId = b.record.key.eventId) : a.record.key = b.record.key :=
  congrArg RecordedEvent.key (same_id_same_record a b same)

theorem same_id_same_observations (a b : RegisteredEvent registry)
    (same : a.record.key.eventId = b.record.key.eventId) :
    a.record.before = b.record.before ∧ a.record.after = b.record.after := by
  rw [same_id_same_record a b same]
  exact ⟨rfl, rfl⟩

theorem missing_record_rejected (id : Nat) (absent : registry.lookup id = none) :
    ¬ ∃ event : RegisteredEvent registry, event.record.key.eventId = id := by
  rintro ⟨event, same⟩
  have present := event.present
  rw [same, absent] at present
  cases present

end RegisteredEvent

-- This pilot's temporal profile checks well-formedness, not causal truth.
-- Overlap is allowed. Both views are bound to their registered endpoint records.
structure CausalHypothesis {u : Universe} {Fact : Type} {registry : EventRegistry u Fact}
    (cause consequence : RegisteredEvent registry) where
  causeView : Interpretation cause.record
  consequenceView : Interpretation consequence.record
  distinct : cause.record.key.eventId ≠ consequence.record.key.eventId
  causeStartsFirst : cause.record.key.start ≤ consequence.record.key.start

namespace CausalHypothesis

variable {u : Universe} {Fact : Type} {registry : EventRegistry u Fact}

theorem no_self (event : RegisteredEvent registry) : ¬ Nonempty (CausalHypothesis event event) :=
  fun ⟨hypothesis⟩ => hypothesis.distinct rfl

theorem no_backwards_start (cause consequence : RegisteredEvent registry)
    (late : consequence.record.key.start < cause.record.key.start) :
    ¬ Nonempty (CausalHypothesis cause consequence) :=
  fun ⟨hypothesis⟩ => (Nat.not_le_of_lt late) hypothesis.causeStartsFirst

theorem ordered_endpoints {cause consequence : RegisteredEvent registry}
    (_ : CausalHypothesis cause consequence) :
    cause.record.key.start ≤ cause.record.key.finish ∧
    consequence.record.key.start ≤ consequence.record.key.finish :=
  ⟨cause.record.ordered, consequence.record.ordered⟩

end CausalHypothesis

namespace Witness

inductive EntityId where
  | hurricane | agent | car | house | document | parkingPlace | owner
  deriving DecidableEq
inductive ActionId where
  | damage | edit | move | leaveUnsecured
  deriving DecidableEq
inductive WorldFact where
  | roofIntact | roofDamaged | documentA | documentB | carOnRoad | carOnParkingPlace | carUnsecured
  deriving DecidableEq

def model : Universe := ⟨EntityId, Nat, ActionId⟩

def hurricane : RecordedEvent model WorldFact :=
  { key := ⟨1, (1 : Nat), ActionId.damage, 0, 1⟩,
    before := FiniteState.ofList [.roofIntact], after := FiniteState.ofList [.roofDamaged],
    ordered := by decide }
def aiAgent : RecordedEvent model WorldFact :=
  { key := ⟨2, (1 : Nat), ActionId.edit, 2, 3⟩,
    before := FiniteState.ofList [.documentA], after := FiniteState.ofList [.documentB],
    ordered := by decide }
def car : RecordedEvent model WorldFact :=
  { key := ⟨3, (1 : Nat), ActionId.move, 4, 5⟩,
    before := FiniteState.ofList [.carOnRoad], after := FiniteState.ofList [.carOnParkingPlace],
    ordered := by decide }
-- An omission need not change a physical state. The attribution profile checks
-- explicit duty/deadline/capability/non-performance evidence separately.
def unsecured : RecordedEvent model WorldFact :=
  { key := ⟨4, (1 : Nat), ActionId.leaveUnsecured, 0, 5⟩,
    before := FiniteState.ofList [.carUnsecured], after := FiniteState.ofList [.carUnsecured],
    ordered := by decide }

def carView : Interpretation car := ⟨⟨1, EntityId.car, EntityId.parkingPlace, none⟩⟩
def ownerView : Interpretation car :=
  ⟨⟨2, EntityId.owner, EntityId.parkingPlace, some EntityId.car⟩⟩
def unsecuredView : Interpretation unsecured := ⟨⟨3, EntityId.owner, EntityId.car, none⟩⟩

def registry : EventRegistry model WorldFact where
  lookup id := match id with
    | 1 => some hurricane
    | 2 => some aiAgent
    | 3 => some car
    | 4 => some unsecured
    | _ => none
  key_matches := by
    intro id event present
    cases id with
    | zero => cases present
    | succ id => cases id with
      | zero => cases present; rfl
      | succ id => cases id with
        | zero => cases present; rfl
        | succ id => cases id with
          | zero => cases present; rfl
          | succ id => cases id with
            | zero => cases present; rfl
            | succ id => cases present

def registeredCar : RegisteredEvent registry := ⟨car, rfl⟩
def registeredUnsecured : RegisteredEvent registry := ⟨unsecured, rfl⟩
def proposedCause : CausalHypothesis registeredUnsecured registeredCar :=
  { causeView := unsecuredView, consequenceView := carView,
    distinct := by decide, causeStartsFirst := by decide }

theorem hurricane_changes_state :
    WorldFact.roofIntact ∈ hurricane.consequence.removed ∧
    WorldFact.roofDamaged ∈ hurricane.consequence.added := by decide
theorem agent_changes_state :
    WorldFact.documentA ∈ aiAgent.consequence.removed ∧
    WorldFact.documentB ∈ aiAgent.consequence.added := by decide
theorem car_changes_state :
    WorldFact.carOnRoad ∈ car.consequence.removed ∧
    WorldFact.carOnParkingPlace ∈ car.consequence.added := by decide

theorem alternative_roles_same_observations :
    ownerView.view.actor = EntityId.owner ∧
    ownerView.view.instrument = some EntityId.car ∧
    carView.before = ownerView.before ∧ carView.after = ownerView.after ∧
    carView.consequence = ownerView.consequence := ⟨rfl, rfl, rfl, rfl, rfl⟩

theorem overlapping_cause_accepted :
    unsecured.key.start ≤ car.key.start ∧ car.key.start < unsecured.key.finish ∧
    Nonempty (CausalHypothesis registeredUnsecured registeredCar) :=
  ⟨by decide, by decide, ⟨proposedCause⟩⟩

theorem self_cause_rejected : ¬ Nonempty (CausalHypothesis registeredCar registeredCar) :=
  CausalHypothesis.no_self _

def ghost : RecordedEvent model WorldFact := {unsecured with key := {unsecured.key with eventId := 3}}

theorem ghost_record_rejected : ¬ ∃ event : RegisteredEvent registry, event.record = ghost := by
  rintro ⟨event, same⟩
  have present := event.present
  rw [same] at present
  have records : car = ghost := Option.some.inj present
  have keys := congrArg (fun record => record.key.action) records
  cases keys

def changedObservations : RecordedEvent model WorldFact :=
  {car with before := FiniteState.ofList [.roofIntact], after := FiniteState.ofList [.documentB]}

theorem changed_observations_rejected :
    ¬ ∃ event : RegisteredEvent registry, event.record = changedObservations := by
  rintro ⟨event, same⟩
  have present := event.present
  rw [same] at present
  have records : car = changedObservations := Option.some.inj present
  have states := congrArg RecordedEvent.before records
  have member : WorldFact.carOnRoad ∈ car.before := by decide
  rw [states] at member
  have absent : WorldFact.carOnRoad ∉ changedObservations.before := by decide
  exact absent member

theorem missing_event_rejected :
    ¬ ∃ event : RegisteredEvent registry, event.record.key.eventId = 99 :=
  RegisteredEvent.missing_record_rejected 99 rfl

end Witness

end NormLabEvents
