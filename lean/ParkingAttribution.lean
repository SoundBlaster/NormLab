import ActionAttribution

-- R4 preparation: the typed parking entrypoint, before runtime/source mapping.
-- Supplied observations/grounds are not a legal or physical truth oracle.
namespace NormLabParkingAttribution

open NormLabRelations NormLabStateRelations NormLabDerivationTraces NormLabEvents
open NormLabActionAttribution

structure Input {u : NormLabActionAttribution.Universe} {Fact : Type} (registry : EventRegistry u.toUniverse Fact) where
  event : RegisteredEvent registry
  interpretation : Interpretation event.record
  humanAnchor : Human u
  kind : Profile.Kind
  facts : List (Literal (Profile.signature u))
  catalog : List (GroundRule (Profile.signature u))

namespace Input

def context {u : NormLabActionAttribution.Universe} {Fact : Type} {registry : EventRegistry u.toUniverse Fact}
    (input : Input (u := u) registry) : HumanContext (u := u) registry :=
  NormLabActionAttribution.humanCandidate input.event input.interpretation input.humanAnchor

end Input

section Entry

variable {u : NormLabActionAttribution.Universe} {Fact : Type} {registry : EventRegistry u.toUniverse Fact}
variable [DecidableEq (Literal (Profile.signature u))]

-- The return type requires registration. No UnboundTransition can substitute.
def propose (input : Input (u := u) registry) : Option (GroundedTransition (u := u) registry) :=
  NormLabActionAttribution.propose input.facts input.catalog input.kind input.context

theorem propose_isSome_iff (input : Input (u := u) registry) :
    (propose input).isSome = true ↔ NormLabActionAttribution.check input.facts input.catalog input.kind input.context = true :=
  NormLabActionAttribution.propose_isSome_iff _ _ _ _

theorem accepted_record (input : Input (u := u) registry)
    (result : GroundedTransition (u := u) registry) (accepted : propose input = some result) :
    result.context.event.record = input.event.record := by
  unfold propose NormLabActionAttribution.propose at accepted
  split at accepted
  · cases accepted; rfl
  · cases accepted

theorem accepted_scope (input : Input (u := u) registry)
    (result : GroundedTransition (u := u) registry) (accepted : propose input = some result) :
    result.context.scope.toEventKey = input.event.record.key := by
  rw [HumanContext.scope_key, accepted_record input result accepted]

end Entry

namespace Witness

inductive EntityId where
  | driver | owner | vehicle | municipality | place
  deriving DecidableEq
inductive ActionId where
  | park | pay
  deriving DecidableEq
inductive WorldFact where
  | vehicleOnRoad | vehicleOnPlace
  deriving DecidableEq

def model : NormLabActionAttribution.Universe :=
  {Entity := EntityId, Episode := Nat, Action := ActionId,
    IsHuman := fun entity => entity = .driver ∨ entity = .owner}

private instance : DecidableEq model.Entity := inferInstanceAs (DecidableEq EntityId)
private instance : DecidableEq (Profile.signature model).Predicate :=
  inferInstanceAs (DecidableEq Profile.Predicate)
private instance : ∀ sort, DecidableEq ((Profile.signature model).Entity sort) := by
  intro sort
  cases sort with
  | human => exact inferInstanceAs (DecidableEq {e : EntityId // e = .driver ∨ e = .owner})
  | entity => exact inferInstanceAs (DecidableEq EntityId)
  | instrument => exact inferInstanceAs (DecidableEq (Option EntityId))
  | episode => exact inferInstanceAs (DecidableEq Nat)
  | action => exact inferInstanceAs (DecidableEq ActionId)
  | time | eventId | interpretationId => exact inferInstanceAs (DecidableEq Nat)

def placement : RecordedEvent model.toUniverse WorldFact :=
  {key := ⟨101, (7 : Nat), ActionId.park, 10, 20⟩,
    before := FiniteState.ofList [.vehicleOnRoad], after := FiniteState.ofList [.vehicleOnPlace],
    ordered := by decide}
def nonpayment : RecordedEvent model.toUniverse WorldFact :=
  {key := ⟨102, (7 : Nat), ActionId.pay, 10, 20⟩,
    before := FiniteState.ofList [.vehicleOnPlace], after := FiniteState.ofList [.vehicleOnPlace],
    ordered := by decide}
def registry : EventRegistry model.toUniverse WorldFact :=
  EventRegistry.ofList [placement, nonpayment] (by decide)
def event : RegisteredEvent registry := ⟨nonpayment, rfl⟩
def view : Interpretation event.record :=
  ⟨⟨1, EntityId.driver, EntityId.municipality, some EntityId.vehicle⟩⟩
def driver : Human model := ⟨EntityId.driver, Or.inl rfl⟩
def context : HumanContext (u := model) registry := NormLabActionAttribution.humanCandidate event view driver
def input : Input (u := model) registry :=
  {event := event, interpretation := view, humanAnchor := driver, kind := .omission,
    facts := Profile.grounds .omission context.scope,
    catalog := [Profile.profileRule .omission context.scope]}

theorem omission_accepted : (propose input).isSome = true := by
  rw [propose_isSome_iff]
  change NormLabActionAttribution.check (Profile.grounds .omission context.scope)
    [Profile.profileRule .omission context.scope] .omission context = true
  simp only [NormLabActionAttribution.check, Profile.check, Profile.certificate, Profile.profileRule,
    Profile.grounds, Tree.verify, Tree.check, Tree.conclusion, List.map_cons, List.map_nil,
    List.attach_cons, List.attach_nil, List.all_cons, List.all_nil]
  decide

theorem driver_not_owner :
    input.context.scope.actor = EntityId.driver ∧
    input.context.scope.actor ≠ EntityId.owner ∧
    input.event.record.key.episode = (7 : Nat) ∧
    input.context.scope.instrument = some EntityId.vehicle := ⟨rfl, by decide, rfl, rfl⟩

def unknownInput : Input (u := model) registry :=
  {input with facts := (remove input.facts
      (FiniteState.ofList [Profile.literal .performed .negative context.scope]))}

theorem unknown_rejected : (propose unknownInput).isNone = true := by
  have rejected : NormLabActionAttribution.check unknownInput.facts unknownInput.catalog unknownInput.kind
      unknownInput.context = false := by
    change NormLabActionAttribution.check
      (remove (Profile.grounds .omission context.scope)
        (FiniteState.ofList [Profile.literal .performed .negative context.scope]))
      [Profile.profileRule .omission context.scope] .omission context = false
    simp only [NormLabActionAttribution.check, Profile.check, Profile.certificate, Profile.profileRule,
      Profile.grounds, Tree.verify, Tree.check, Tree.conclusion, List.map_cons, List.map_nil,
      List.attach_cons, List.attach_nil, List.all_cons, List.all_nil]
    decide
  simp [propose, NormLabActionAttribution.propose, rejected]

-- Duplicate ID with different action/observations is rejected, not overwritten.
def reusedId : RecordedEvent model.toUniverse WorldFact :=
  {nonpayment with key := {nonpayment.key with eventId := 101}}

theorem duplicate_ids_rejected : EventRegistry.ofList? [placement, reusedId] = none := by
  apply EventRegistry.ofList?_duplicate_rejected
  decide

end Witness

end NormLabParkingAttribution
