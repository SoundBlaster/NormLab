import DerivationTraces

-- R3: bounded formal attribution under explicitly supplied facts and rules.
-- No legal defaults, real-world causality oracle or parking runtime adapter.
namespace NormLabActionAttribution

open NormLabRelations NormLabStateRelations NormLabDerivationTraces

structure Universe where
  Entity : Type
  IsHuman : Entity → Prop
  Episode : Type
  Action : Type

abbrev Human (u : Universe) := { entity : u.Entity // u.IsHuman entity }

-- Actor is a role of any entity, including an abstract community. HumanAnchor
-- is a separate participant used by this bounded human-grounding profile.
structure Context (u : Universe) where
  actor : u.Entity
  humanAnchor : Human u
  target : u.Entity
  instrument : Option u.Entity
  episode : u.Episode
  action : u.Action
  start : Nat
  finish : Nat

inductive Kind where
  | action | omission
  deriving DecidableEq

inductive SortId where
  | human | entity | instrument | episode | action | time

inductive Predicate where
  | attributed | performed | required | deadlineElapsed | capable | exception
  | actionGrounded | omissionGrounded | relationActive | breachRecorded
  deriving DecidableEq

def Entity (u : Universe) : SortId → Type
  | .human => Human u
  | .entity => u.Entity
  | .instrument => Option u.Entity
  | .episode => u.Episode
  | .action => u.Action
  | .time => Nat

def signature (u : Universe) : Signature :=
  { SortId := SortId, Entity := Entity u, Predicate := Predicate,
    arity := fun _ => [.entity, .human, .entity, .instrument, .episode, .action, .time, .time] }

def arguments {u : Universe} (ctx : Context u) :
    Args (signature u) [.entity, .human, .entity, .instrument, .episode, .action, .time, .time] :=
  .cons ctx.actor (.cons ctx.humanAnchor (.cons ctx.target (.cons ctx.instrument (.cons ctx.episode
    (.cons ctx.action (.cons ctx.start (.cons ctx.finish .nil)))))))

def literal {u : Universe} (predicate : Predicate) (polarity : Polarity)
    (ctx : Context u) : Literal (signature u) := ⟨polarity, ⟨predicate, arguments ctx⟩⟩

def contextOf {u : Universe} (value : Literal (signature u)) : Context u :=
  match value.atom.args with
  | .cons actor (.cons humanAnchor (.cons target (.cons instrument (.cons episode
      (.cons action (.cons start (.cons finish .nil))))))) =>
      ⟨actor, humanAnchor, target, instrument, episode, action, start, finish⟩

@[simp] theorem contextOf_literal {u : Universe} (p : Predicate) (s : Polarity)
    (ctx : Context u) : contextOf (literal p s ctx) = ctx := by cases ctx; rfl

theorem literal_context_injective {u : Universe} {p q : Predicate} {s t : Polarity}
    {a b : Context u} (same : literal p s a = literal q t b) : a = b := by
  simpa only [contextOf_literal] using congrArg contextOf same

def opposite {sig : Signature} (value : Literal sig) : Literal sig :=
  { value with polarity := match value.polarity with
      | .positive => .negative
      | .negative => .positive }

-- Performed/non-performance describe the selected human anchor's contribution;
-- attributed is the explicit model relation connecting it to the actor.
def grounds {u : Universe} (kind : Kind) (ctx : Context u) : List (Literal (signature u)) :=
  match kind with
  | .action => [literal .attributed .positive ctx, literal .performed .positive ctx]
  | .omission => [literal .attributed .positive ctx,
      literal .required .positive ctx, literal .deadlineElapsed .positive ctx,
      literal .capable .positive ctx, literal .exception .negative ctx,
      literal .performed .negative ctx]

def eligible {u : Universe} (kind : Kind) (ctx : Context u) : Literal (signature u) :=
  literal (match kind with | .action => .actionGrounded | .omission => .omissionGrounded)
    .positive ctx

def effect {u : Universe} (kind : Kind) (ctx : Context u) : Literal (signature u) :=
  literal (match kind with | .action => .relationActive | .omission => .breachRecorded)
    .positive ctx

def profileRule {u : Universe} (kind : Kind) (ctx : Context u) : GroundRule (signature u) :=
  ⟨grounds kind ctx, eligible kind ctx⟩

-- The caller cannot substitute an unrelated tree or use an input eligibility
-- fact as a shortcut. This tree always cites every selected profile premise.
def certificate {u : Universe} (kind : Kind) (ctx : Context u) : Tree (signature u) :=
  .step (profileRule kind ctx) ((grounds kind ctx).map Tree.fact)

theorem certificate_uses_facts {u : Universe} (kind : Kind) (ctx : Context u) :
    (certificate kind ctx).usedFacts = grounds kind ctx := by
  cases kind <;> simp [certificate, grounds, Tree.usedFacts]

theorem certificate_uses_rule {u : Universe} (kind : Kind) (ctx : Context u) :
    (certificate kind ctx).usedRules = [profileRule kind ctx] := by
  cases kind <;> simp [certificate, grounds, Tree.usedRules]

section Check

variable {u : Universe} [DecidableEq (Literal (signature u))]

def clear (facts : List (Literal (signature u))) (value : Literal (signature u)) : Bool :=
  decide (value ∈ facts) && !(decide (opposite value ∈ facts))

theorem clear_iff (facts : List (Literal (signature u))) (value : Literal (signature u)) :
    clear facts value = true ↔ value ∈ facts ∧ opposite value ∉ facts := by
  simp [clear]

def check (facts : List (Literal (signature u))) (catalog : List (GroundRule (signature u)))
    (kind : Kind) (ctx : Context u) : Bool :=
  decide (ctx.start ≤ ctx.finish) && (grounds kind ctx).all (clear facts) &&
    !(decide (opposite (effect kind ctx) ∈ facts)) &&
    Tree.verify facts catalog (eligible kind ctx) (certificate kind ctx)

theorem check_iff (facts : List (Literal (signature u)))
    (catalog : List (GroundRule (signature u))) (kind : Kind) (ctx : Context u) :
    check facts catalog kind ctx = true ↔
      ctx.start ≤ ctx.finish ∧
      (∀ value ∈ grounds kind ctx, value ∈ facts ∧ opposite value ∉ facts) ∧
      opposite (effect kind ctx) ∉ facts ∧
      Tree.verify facts catalog (eligible kind ctx) (certificate kind ctx) = true := by
  simp [check, List.all_eq_true, clear_iff, and_assoc]

theorem checked_provenance {facts : List (Literal (signature u))}
    {catalog : List (GroundRule (signature u))} {kind : Kind} {ctx : Context u}
    (accepted : check facts catalog kind ctx = true) :
    Derivable facts catalog (eligible kind ctx) :=
  Tree.verify_sound ((check_iff _ _ _ _).mp accepted).2.2.2

theorem checked_rule_authorized {facts : List (Literal (signature u))}
    {catalog : List (GroundRule (signature u))} {kind : Kind} {ctx : Context u}
    (accepted : check facts catalog kind ctx = true) : profileRule kind ctx ∈ catalog := by
  have checked := ((check_iff _ _ _ _).mp accepted).2.2.2
  have valid := ((Tree.verify_iff _ _ _ _).mp checked).2
  have used : profileRule kind ctx ∈ (certificate kind ctx).usedRules := by
    rw [certificate_uses_rule]; simp
  exact Tree.valid_uses_rules valid used

theorem checked_action_has_performance {facts : List (Literal (signature u))}
    {catalog : List (GroundRule (signature u))} {ctx : Context u}
    (accepted : check facts catalog .action ctx = true) :
    literal .performed .positive ctx ∈ facts ∧ literal .performed .negative ctx ∉ facts := by
  exact ((check_iff _ _ _ _).mp accepted).2.1 _ (by simp [grounds])

theorem checked_actor_attributed {facts : List (Literal (signature u))}
    {catalog : List (GroundRule (signature u))} {kind : Kind} {ctx : Context u}
    (accepted : check facts catalog kind ctx = true) :
    literal .attributed .positive ctx ∈ facts ∧ literal .attributed .negative ctx ∉ facts := by
  apply ((check_iff _ _ _ _).mp accepted).2.1
  cases kind <;> simp [grounds]

theorem unattributed_actor_rejected {facts : List (Literal (signature u))}
    {catalog : List (GroundRule (signature u))} {kind : Kind} {ctx : Context u}
    (missing : literal .attributed .positive ctx ∉ facts) : check facts catalog kind ctx = false := by
  cases accepted : check facts catalog kind ctx with
  | false => rfl
  | true => exact False.elim (missing (checked_actor_attributed accepted).1)

theorem checked_omission_has_nonperformance {facts : List (Literal (signature u))}
    {catalog : List (GroundRule (signature u))} {ctx : Context u}
    (accepted : check facts catalog .omission ctx = true) :
    literal .performed .negative ctx ∈ facts ∧ literal .performed .positive ctx ∉ facts := by
  exact ((check_iff _ _ _ _).mp accepted).2.1 _ (by simp [grounds])

theorem checked_omission_conditions {facts : List (Literal (signature u))}
    {catalog : List (GroundRule (signature u))} {ctx : Context u}
    (accepted : check facts catalog .omission ctx = true) :
    literal .required .positive ctx ∈ facts ∧ literal .deadlineElapsed .positive ctx ∈ facts ∧
    literal .capable .positive ctx ∈ facts ∧ literal .exception .negative ctx ∈ facts ∧
    literal .exception .positive ctx ∉ facts := by
  have supported := ((check_iff _ _ _ _).mp accepted).2.1
  exact ⟨(supported _ (by simp [grounds])).1, (supported _ (by simp [grounds])).1,
    (supported _ (by simp [grounds])).1, supported _ (by simp [grounds])⟩

theorem checked_has_scoped_fact {facts : List (Literal (signature u))}
    {catalog : List (GroundRule (signature u))} {kind : Kind} {ctx : Context u}
    (accepted : check facts catalog kind ctx = true) :
    ∃ value ∈ facts, contextOf value = ctx := by
  cases kind with
  | action => exact ⟨_, (checked_action_has_performance accepted).1, contextOf_literal _ _ _⟩
  | omission => exact ⟨_, (checked_omission_has_nonperformance accepted).1, contextOf_literal _ _ _⟩

-- A schema-level identity result, not just a single wrong-person witness.
theorem checked_scope_preserved {facts : List (Literal (signature u))}
    {catalog : List (GroundRule (signature u))} {kind : Kind} {ctx original : Context u}
    (allInScope : ∀ value ∈ facts, contextOf value = original)
    (accepted : check facts catalog kind ctx = true) : ctx = original := by
  obtain ⟨value, member, same⟩ := checked_has_scoped_fact accepted
  exact same.symm.trans (allInScope value member)

theorem unknown_nonperformance_rejected {facts : List (Literal (signature u))}
    {catalog : List (GroundRule (signature u))} {ctx : Context u}
    (missing : literal .performed .negative ctx ∉ facts) :
    check facts catalog .omission ctx = false := by
  cases accepted : check facts catalog .omission ctx with
  | false => rfl
  | true => exact False.elim (missing (checked_omission_has_nonperformance accepted).1)

theorem opposed_nonperformance_rejected {facts : List (Literal (signature u))}
    {catalog : List (GroundRule (signature u))} {ctx : Context u}
    (performed : literal .performed .positive ctx ∈ facts) :
    check facts catalog .omission ctx = false := by
  cases accepted : check facts catalog .omission ctx with
  | false => rfl
  | true => exact False.elim ((checked_omission_has_nonperformance accepted).2 performed)

theorem unauthorized_profile_rejected {facts : List (Literal (signature u))}
    {catalog : List (GroundRule (signature u))} {kind : Kind} {ctx : Context u}
    (missing : profileRule kind ctx ∉ catalog) : check facts catalog kind ctx = false := by
  cases accepted : check facts catalog kind ctx with
  | false => rfl
  | true => exact False.elim (missing (checked_rule_authorized accepted))

def before (facts : List (Literal (signature u))) : StateRelations (signature u) :=
  FiniteState.ofList facts

-- An explicit append-only profile effect, not insertion of the whole closure.
def after (facts : List (Literal (signature u))) (kind : Kind) (ctx : Context u) :
    StateRelations (signature u) := (before facts).union (FiniteState.ofList [effect kind ctx])

def consequence (facts : List (Literal (signature u))) (kind : Kind) (ctx : Context u) :
    Delta (Literal (signature u)) := Delta.between (before facts) (after facts kind ctx)

theorem mem_after (facts : List (Literal (signature u))) (kind : Kind) (ctx : Context u)
    (value : Literal (signature u)) :
    value ∈ after facts kind ctx ↔ value ∈ facts ∨ value = effect kind ctx := by
  simp [after, before]

theorem frame {facts : List (Literal (signature u))} {kind : Kind} {ctx : Context u}
    (value : Literal (signature u)) (untouched : value ≠ effect kind ctx) :
    value ∈ after facts kind ctx ↔ value ∈ facts := by simp [mem_after, untouched]

theorem exact_added (facts : List (Literal (signature u))) (kind : Kind) (ctx : Context u)
    (value : Literal (signature u)) :
    value ∈ (consequence facts kind ctx).added ↔
      value = effect kind ctx ∧ value ∉ facts := by
  simp only [consequence, Delta.mem_added, mem_after, before, FiniteState.mem_ofList]
  constructor
  · rintro ⟨member | same, absent⟩
    · exact False.elim (absent member)
    · exact ⟨same, absent⟩
  · rintro ⟨same, absent⟩
    exact ⟨Or.inr same, absent⟩

theorem nothing_removed (facts : List (Literal (signature u))) (kind : Kind) (ctx : Context u) :
    (consequence facts kind ctx).removed = FiniteState.empty := by
  apply FiniteState.ext
  intro value
  rw [consequence, Delta.mem_removed]
  simp only [before, FiniteState.mem_ofList, mem_after, FiniteState.not_mem_empty]
  constructor
  · exact fun ⟨member, absent⟩ => absent (Or.inl member)
  · intro impossible; cases impossible

theorem consequence_roundtrip (facts : List (Literal (signature u))) (kind : Kind)
    (ctx : Context u) :
    Delta.apply (before facts) (consequence facts kind ctx) = after facts kind ctx :=
  Delta.roundtrip _ _

-- Only a checked input can inhabit GroundedTransition. After-state, certificate
-- and delta are computed methods; callers cannot attach arbitrary output edits.
structure GroundedTransition (u : Universe) [DecidableEq (Literal (signature u))] where
  kind : Kind
  context : Context u
  facts : List (Literal (signature u))
  catalog : List (GroundRule (signature u))
  accepted : check facts catalog kind context = true

def propose (facts : List (Literal (signature u))) (catalog : List (GroundRule (signature u)))
    (kind : Kind) (ctx : Context u) : Option (GroundedTransition u) :=
  if accepted : check facts catalog kind ctx = true then
    some ⟨kind, ctx, facts, catalog, accepted⟩ else none

theorem propose_isSome_iff (facts : List (Literal (signature u)))
    (catalog : List (GroundRule (signature u))) (kind : Kind) (ctx : Context u) :
    (propose facts catalog kind ctx).isSome = true ↔ check facts catalog kind ctx = true := by
  unfold propose
  split <;> simp_all

namespace GroundedTransition

def before (transition : GroundedTransition u) := NormLabActionAttribution.before transition.facts
def after (transition : GroundedTransition u) :=
  NormLabActionAttribution.after transition.facts transition.kind transition.context
def consequence (transition : GroundedTransition u) :=
  NormLabActionAttribution.consequence transition.facts transition.kind transition.context
def certificate (transition : GroundedTransition u) :=
  NormLabActionAttribution.certificate transition.kind transition.context

theorem provenance (transition : GroundedTransition u) :
    Derivable transition.facts transition.catalog (eligible transition.kind transition.context) :=
  checked_provenance transition.accepted

theorem roundtrip (transition : GroundedTransition u) :
    Delta.apply transition.before transition.consequence = transition.after :=
  consequence_roundtrip _ _ _

-- Every newly introduced state fact is tied to the very same actor/context,
-- an explicit attribution fact, and the checked grounding derivation.
theorem added_has_grounds (transition : GroundedTransition u)
    (value : Literal (signature u)) (added : value ∈ transition.consequence.added) :
    value = effect transition.kind transition.context ∧
    literal .attributed .positive transition.context ∈ transition.facts ∧
    Derivable transition.facts transition.catalog (eligible transition.kind transition.context) :=
  ⟨((exact_added _ _ _ _).mp added).1,
    (checked_actor_attributed transition.accepted).1, transition.provenance⟩

end GroundedTransition

end Check

namespace Witness

inductive EntityId where
  | alice | bob | community | vehicle | place
  deriving DecidableEq
inductive ActionId where
  | placeObject | pay | selfCare
  deriving DecidableEq

-- Community is deliberately an abstract entity, not a list/subtype of humans.
def model : Universe :=
  { Entity := EntityId, IsHuman := fun e => e = .alice ∨ e = .bob,
    Episode := Nat, Action := ActionId }

private instance : DecidableEq model.Entity := inferInstanceAs (DecidableEq EntityId)
private instance : DecidableEq model.Episode := inferInstanceAs (DecidableEq Nat)
private instance : DecidableEq model.Action := inferInstanceAs (DecidableEq ActionId)
private instance (e : model.Entity) : Decidable (model.IsHuman e) :=
  inferInstanceAs (Decidable (e = EntityId.alice ∨ e = EntityId.bob))

private instance : DecidableEq (signature model).Predicate :=
  inferInstanceAs (DecidableEq Predicate)
private instance : ∀ sort, DecidableEq ((signature model).Entity sort) := by
  intro sort
  cases sort with
  | human => exact inferInstanceAs (DecidableEq {e : EntityId // e = .alice ∨ e = .bob})
  | entity => exact inferInstanceAs (DecidableEq EntityId)
  | instrument => exact inferInstanceAs (DecidableEq (Option EntityId))
  | episode => exact inferInstanceAs (DecidableEq Nat)
  | action => exact inferInstanceAs (DecidableEq ActionId)
  | time => exact inferInstanceAs (DecidableEq Nat)

def ctx : Context model :=
  { actor := EntityId.alice, humanAnchor := ⟨EntityId.alice, Or.inl rfl⟩,
    target := EntityId.place, instrument := some EntityId.vehicle,
    episode := (1 : Nat), action := ActionId.placeObject, start := 10, finish := 20 }
def abstractCtx : Context model := { ctx with actor := EntityId.community }
def omissionCtx : Context model := { abstractCtx with action := ActionId.pay }
def selfCtx : Context model :=
  { ctx with target := EntityId.alice, instrument := none, action := ActionId.selfCare }
def actionFacts := grounds .action ctx
def abstractFacts := grounds .action abstractCtx
def omissionFacts := grounds .omission omissionCtx
def actionCatalog := [profileRule .action ctx]
def abstractCatalog := [profileRule .action abstractCtx]
def omissionCatalog := [profileRule .omission omissionCtx]

theorem direct_action_accepted : check actionFacts actionCatalog .action ctx = true := by
  simp [check, clear, certificate, profileRule, grounds, Tree.verify, Tree.check, Tree.conclusion]
  decide

theorem abstract_actor_accepted : check abstractFacts abstractCatalog .action abstractCtx = true := by
  simp [check, clear, certificate, profileRule, grounds, Tree.verify, Tree.check, Tree.conclusion]
  decide

theorem abstract_actor_is_not_human :
    ¬ model.IsHuman abstractCtx.actor ∧
    abstractCtx.humanAnchor.val = EntityId.alice ∧
    abstractCtx.actor ≠ abstractCtx.humanAnchor.val := by decide

theorem omission_accepted : check omissionFacts omissionCatalog .omission omissionCtx = true := by
  simp only [check, certificate, profileRule, grounds, Tree.verify, Tree.check, Tree.conclusion,
    List.map_cons, List.map_nil, List.attach_cons, List.attach_nil, List.all_cons, List.all_nil]
  decide

theorem self_action_accepted :
    selfCtx.actor = selfCtx.target ∧
    check (grounds .action selfCtx) [profileRule .action selfCtx] .action selfCtx = true := by
  simp only [check, certificate, profileRule, grounds, Tree.verify, Tree.check, Tree.conclusion,
    List.map_cons, List.map_nil, List.attach_cons, List.attach_nil, List.all_cons, List.all_nil]
  decide

theorem attribution_cannot_be_skipped :
    check [literal .performed .positive abstractCtx] abstractCatalog .action abstractCtx = false := by
  apply unattributed_actor_rejected
  decide

theorem scope_substitution_rejected :
    check actionFacts [profileRule .action {ctx with actor := EntityId.bob}]
      .action {ctx with actor := EntityId.bob} = false ∧
    check abstractFacts [profileRule .action {abstractCtx with humanAnchor := ⟨EntityId.bob, Or.inr rfl⟩}]
      .action {abstractCtx with humanAnchor := ⟨EntityId.bob, Or.inr rfl⟩} = false ∧
    check actionFacts [profileRule .action {ctx with target := EntityId.vehicle}]
      .action {ctx with target := EntityId.vehicle} = false ∧
    check actionFacts [profileRule .action {ctx with instrument := none}]
      .action {ctx with instrument := none} = false ∧
    check actionFacts [profileRule .action {ctx with episode := (2 : Nat)}]
      .action {ctx with episode := (2 : Nat)} = false ∧
    check actionFacts [profileRule .action {ctx with action := ActionId.pay}]
      .action {ctx with action := ActionId.pay} = false ∧
    check actionFacts [profileRule .action {ctx with finish := 21}]
      .action {ctx with finish := 21} = false := by
  simp only [check, certificate, profileRule, grounds, Tree.verify, Tree.check, Tree.conclusion,
    List.map_cons, List.map_nil, List.attach_cons, List.attach_nil, List.all_cons, List.all_nil]
  decide

def unknownFacts := remove omissionFacts (FiniteState.ofList [literal .performed .negative omissionCtx])

theorem unknown_is_not_omission : check unknownFacts omissionCatalog .omission omissionCtx = false := by
  apply unknown_nonperformance_rejected
  decide

theorem conflict_is_not_omission :
    check (literal .performed .positive omissionCtx :: omissionFacts)
      omissionCatalog .omission omissionCtx = false := by
  apply opposed_nonperformance_rejected
  simp

theorem missing_conditions_rejected :
    check (remove omissionFacts (FiniteState.ofList [literal .deadlineElapsed .positive omissionCtx]))
      omissionCatalog .omission omissionCtx = false ∧
    check (remove omissionFacts (FiniteState.ofList [literal .capable .positive omissionCtx]))
      omissionCatalog .omission omissionCtx = false ∧
    check (remove omissionFacts (FiniteState.ofList [literal .exception .negative omissionCtx]))
      omissionCatalog .omission omissionCtx = false := by
  simp [check, clear, certificate, profileRule, grounds, Tree.verify, Tree.check, Tree.conclusion] <;>
    decide

theorem direct_candidate_cannot_bypass :
    check [eligible .action ctx] actionCatalog .action ctx = false := by
  apply unattributed_actor_rejected
  decide

def unrelatedRule : GroundRule (signature model) := ⟨[], eligible .action ctx⟩

theorem unrelated_rule_cannot_bypass :
    Derivable actionFacts [unrelatedRule] (eligible .action ctx) ∧
    check actionFacts [unrelatedRule] .action ctx = false := by
  constructor
  · apply Derivable.application (rule := unrelatedRule) (by simp)
    intro _ member
    cases member
  · apply unauthorized_profile_rejected
    decide

theorem nonempty_exact_effect :
    effect .action ctx ∈ (consequence actionFacts .action ctx).added ∧
    (consequence actionFacts .action ctx).removed = FiniteState.empty := by
  constructor
  · rw [exact_added]
    exact ⟨rfl, by decide⟩
  · exact nothing_removed _ _ _

def otherCtx : Context model := {ctx with actor := EntityId.bob, episode := (99 : Nat)}
def unrelatedConflict :=
  [literal .performed .positive otherCtx, literal .performed .negative otherCtx]
def withUnrelatedConflict := actionFacts ++ unrelatedConflict

theorem unrelated_conflict_retained :
    check withUnrelatedConflict actionCatalog .action ctx = true ∧
    literal .performed .positive otherCtx ∈ after withUnrelatedConflict .action ctx ∧
    literal .performed .negative otherCtx ∈ after withUnrelatedConflict .action ctx := by
  constructor
  · simp [check, clear, certificate, profileRule, grounds, Tree.verify, Tree.check, Tree.conclusion]
    decide
  · constructor <;> apply (mem_after _ _ _ _).mpr <;> apply Or.inl <;>
      simp [withUnrelatedConflict, unrelatedConflict]

theorem output_is_not_derived_closure :
    eligible .action ctx ∉ after actionFacts .action ctx := by
  rw [mem_after]
  decide

end Witness

end NormLabActionAttribution
