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

namespace EventRegistry

variable {u : Universe} {Fact : Type}

private def lookupRecords (records : List (RecordedEvent u Fact)) (id : Nat) :
    Option (RecordedEvent u Fact) :=
  match records with
  | [] => none
  | first :: rest => if first.key.eventId = id then some first else lookupRecords rest id

private theorem lookupRecords_key (records : List (RecordedEvent u Fact)) :
    ∀ id event, lookupRecords records id = some event → event.key.eventId = id := by
  induction records with
  | nil => intro id event found; cases found
  | cons first rest ih =>
    intro id event found
    by_cases same : first.key.eventId = id
    · simp only [lookupRecords, if_pos same] at found
      cases found
      exact same
    · simp only [lookupRecords, if_neg same] at found
      exact ih id event found

private theorem lookupRecords_member (records : List (RecordedEvent u Fact)) :
    ∀ (_ : (records.map (fun event => event.key.eventId)).Nodup) (event : RecordedEvent u Fact),
      event ∈ records → lookupRecords records event.key.eventId = some event := by
  induction records with
  | nil => intro unique event member; cases member
  | cons first rest ih =>
    intro unique event member
    have unique' : first.key.eventId ∉ rest.map (fun event => event.key.eventId) ∧
        (rest.map (fun event => event.key.eventId)).Nodup := by
      simpa only [List.map_cons, List.nodup_cons] using unique
    rcases List.mem_cons.mp member with same | member
    · subst event
      simp [lookupRecords]
    · have different : first.key.eventId ≠ event.key.eventId := by
        intro same
        exact unique'.1 (List.mem_map.mpr ⟨event, member, same.symm⟩)
      rw [lookupRecords, if_neg different]
      exact ih unique'.2 event member

private theorem lookupRecords_only_members (records : List (RecordedEvent u Fact)) :
    ∀ id event, lookupRecords records id = some event → event ∈ records := by
  induction records with
  | nil => intro id event found; cases found
  | cons first rest ih =>
    intro id event found
    by_cases same : first.key.eventId = id
    · simp only [lookupRecords, if_pos same] at found
      cases found
      exact List.mem_cons.mpr (Or.inl rfl)
    · simp only [lookupRecords, if_neg same] at found
      exact List.mem_cons.mpr (Or.inr (ih id event found))

-- The proof requirement excludes duplicate IDs even when their other fields
-- differ. No first/last-write-wins constructor is exposed.
def ofList (records : List (RecordedEvent u Fact))
    (_unique : (records.map (fun event => event.key.eventId)).Nodup) : EventRegistry u Fact :=
  ⟨lookupRecords records, lookupRecords_key records⟩

theorem ofList_lookup (records : List (RecordedEvent u Fact))
    (unique : (records.map (fun event => event.key.eventId)).Nodup)
    (event : RecordedEvent u Fact) (member : event ∈ records) :
    (ofList records unique).lookup event.key.eventId = some event :=
  lookupRecords_member records unique event member

theorem ofList_lookup_iff (records : List (RecordedEvent u Fact))
    (unique : (records.map (fun event => event.key.eventId)).Nodup)
    (id : Nat) (event : RecordedEvent u Fact) :
    (ofList records unique).lookup id = some event ↔ event ∈ records ∧ event.key.eventId = id := by
  constructor
  · intro found
    exact ⟨lookupRecords_only_members records id event found, lookupRecords_key records id event found⟩
  · rintro ⟨member, same⟩
    rw [← same]
    exact ofList_lookup records unique event member

def ofList? (records : List (RecordedEvent u Fact)) : Option (EventRegistry u Fact) :=
  if unique : (records.map (fun event => event.key.eventId)).Nodup then
    some (ofList records unique) else none

theorem ofList?_isSome_iff (records : List (RecordedEvent u Fact)) :
    (ofList? records).isSome = true ↔ (records.map (fun event => event.key.eventId)).Nodup := by
  unfold ofList?
  split <;> simp_all

theorem ofList?_duplicate_rejected (records : List (RecordedEvent u Fact))
    (duplicate : ¬ (records.map (fun event => event.key.eventId)).Nodup) :
    ofList? records = none := by simp [ofList?, duplicate]

end EventRegistry

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

def registry : EventRegistry model WorldFact :=
  EventRegistry.ofList [hurricane, aiAgent, car, unsecured] (by decide)

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
