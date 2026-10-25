import StateRelations

-- General events and interpretation-relative roles. No Human type, causal
-- oracle or normative responsibility rule is required by this layer.
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

structure Context (u : Universe) extends EventKey u, RoleView u

-- Before/after are supplied observations in a chosen state projection. This
-- records a transition; it does not prove physical causality or responsibility.
structure RecordedTransition (u : Universe) (Fact : Type) where
  context : Context u
  before : FiniteState Fact
  after : FiniteState Fact
  ordered : context.start ≤ context.finish

namespace RecordedTransition

variable {u : Universe} {Fact : Type} [DecidableEq Fact]

def consequence (transition : RecordedTransition u Fact) : Delta Fact :=
  Delta.between transition.before transition.after

theorem roundtrip (transition : RecordedTransition u Fact) :
    Delta.apply transition.before transition.consequence = transition.after := Delta.roundtrip _ _

theorem added_iff (transition : RecordedTransition u Fact) (fact : Fact) :
    fact ∈ transition.consequence.added ↔ fact ∈ transition.after ∧ fact ∉ transition.before :=
  Delta.mem_added _ _ _

theorem removed_iff (transition : RecordedTransition u Fact) (fact : Fact) :
    fact ∈ transition.consequence.removed ↔ fact ∈ transition.before ∧ fact ∉ transition.after :=
  Delta.mem_removed _ _ _

-- Role changes do not change event identity, boundaries or observations.
def reinterpret (transition : RecordedTransition u Fact) (view : RoleView u) :
    RecordedTransition u Fact :=
  { context := ⟨transition.context.toEventKey, view⟩,
    before := transition.before, after := transition.after, ordered := transition.ordered }

omit [DecidableEq Fact] in
theorem reinterpret_event (transition : RecordedTransition u Fact) (view : RoleView u) :
    (transition.reinterpret view).context.toEventKey = transition.context.toEventKey := rfl

omit [DecidableEq Fact] in
theorem reinterpret_states (transition : RecordedTransition u Fact) (view : RoleView u) :
    (transition.reinterpret view).before = transition.before ∧
    (transition.reinterpret view).after = transition.after := ⟨rfl, rfl⟩

theorem reinterpret_consequence (transition : RecordedTransition u Fact) (view : RoleView u) :
    (transition.reinterpret view).consequence = transition.consequence := rfl

omit [DecidableEq Fact] in
theorem different_event_is_not_reinterpretation (transition : RecordedTransition u Fact)
    (view : RoleView u) (other : EventKey u) (different : other ≠ transition.context.toEventKey) :
    (transition.reinterpret view).context.toEventKey ≠ other := fun same => different same.symm

end RecordedTransition

-- An asserted causal hypothesis references descriptions of events.
-- It carries no derived human anchor, role assignment or responsibility result.
structure CausalHypothesis (u : Universe) where
  cause : EventKey u
  consequence : EventKey u
  interpretationId : Nat

namespace Witness

inductive EntityId where
  | hurricane | agent | car | house | document | parkingPlace | owner
  deriving DecidableEq
inductive ActionId where
  | damage | edit | move | leaveUnsecured
  deriving DecidableEq
inductive WorldFact where
  | roofIntact | roofDamaged | documentA | documentB | carOnRoad | carOnParkingPlace
  deriving DecidableEq

-- This universe has no human classification or Human constructor at all.
def model : Universe := ⟨EntityId, Nat, ActionId⟩

def hurricane : RecordedTransition model WorldFact :=
  { context := ⟨⟨1, (1 : Nat), ActionId.damage, 0, 1⟩,
      ⟨1, EntityId.hurricane, EntityId.house, none⟩⟩,
    before := FiniteState.ofList [.roofIntact], after := FiniteState.ofList [.roofDamaged],
    ordered := by decide }
def aiAgent : RecordedTransition model WorldFact :=
  { context := ⟨⟨2, (1 : Nat), ActionId.edit, 2, 3⟩,
      ⟨1, EntityId.agent, EntityId.document, none⟩⟩,
    before := FiniteState.ofList [.documentA], after := FiniteState.ofList [.documentB],
    ordered := by decide }
def car : RecordedTransition model WorldFact :=
  { context := ⟨⟨3, (1 : Nat), ActionId.move, 4, 5⟩,
      ⟨1, EntityId.car, EntityId.parkingPlace, none⟩⟩,
    before := FiniteState.ofList [.carOnRoad], after := FiniteState.ofList [.carOnParkingPlace],
    ordered := by decide }

theorem hurricane_changes_state :
    WorldFact.roofIntact ∈ hurricane.consequence.removed ∧
    WorldFact.roofDamaged ∈ hurricane.consequence.added := by decide

theorem agent_changes_state :
    WorldFact.documentA ∈ aiAgent.consequence.removed ∧
    WorldFact.documentB ∈ aiAgent.consequence.added := by decide

theorem car_changes_state :
    WorldFact.carOnRoad ∈ car.consequence.removed ∧
    WorldFact.carOnParkingPlace ∈ car.consequence.added := by decide

-- A candidate role interpretation, not a determination of the owner's conduct
-- or liability. Human review may choose or reject this view independently.
def ownerView : RoleView model :=
  {interpretationId := 2, actor := EntityId.owner, target := EntityId.parkingPlace,
    instrument := some EntityId.car}

theorem alternative_roles_same_observations :
    (car.reinterpret ownerView).context.actor = EntityId.owner ∧
    (car.reinterpret ownerView).context.instrument = some EntityId.car ∧
    (car.reinterpret ownerView).before = car.before ∧
    (car.reinterpret ownerView).after = car.after ∧
    (car.reinterpret ownerView).consequence = car.consequence :=
  ⟨rfl, rfl, rfl, rfl, rfl⟩

def unsecured : EventKey model :=
  {eventId := 4, episode := (1 : Nat), action := ActionId.leaveUnsecured, start := 0, finish := 1}
def proposedCause : CausalHypothesis model := ⟨unsecured, car.context.toEventKey, 2⟩

theorem predecessor_is_a_separate_event :
    proposedCause.cause ≠ proposedCause.consequence ∧
    (car.reinterpret ownerView).context.toEventKey ≠ unsecured := by
  have different : unsecured ≠ car.context.toEventKey := by
    intro same
    have impossible := congrArg EventKey.eventId same
    cases impossible
  exact ⟨different, RecordedTransition.different_event_is_not_reinterpretation _ _ _ different⟩

end Witness

end NormLabEvents
