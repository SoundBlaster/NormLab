import StateRelations

-- R2b: a finite certificate in Type, independent of proof search or legal rules.
namespace NormLabDerivationTraces

open NormLabRelations NormLabStateRelations

inductive Tree (sig : Signature) where
  | fact : Literal sig → Tree sig
  | step : GroundRule sig → List (Tree sig) → Tree sig

namespace Tree

variable {sig : Signature}

theorem inductionTree {motive : Tree sig → Prop}
    (factCase : ∀ literal, motive (.fact literal))
    (stepCase : ∀ rule children, (∀ child ∈ children, motive child) →
      motive (.step rule children)) (tree : Tree sig) : motive tree :=
  Tree.rec (motive_1 := motive)
    (motive_2 := fun children => ∀ child ∈ children, motive child)
    factCase stepCase
    (fun _ member => by cases member)
    (fun head _ hh ht child member => by
      cases member with
      | head => exact hh
      | tail _ rest => exact ht child rest) tree

def conclusion : Tree sig → Literal sig
  | .fact literal => literal
  | .step rule _ => rule.conclusion

def usedFacts : Tree sig → List (Literal sig)
  | .fact literal => [literal]
  | .step _ children => children.flatMap usedFacts

def usedRules : Tree sig → List (GroundRule sig)
  | .fact _ => []
  | .step rule children => rule :: children.flatMap usedRules

-- Exact ordered premise correspondence also rejects missing/extra subtrees.
-- Unlike Tree, Valid is a logical judgement; checking it is implemented below.
inductive Valid (facts : List (Literal sig)) (rules : List (GroundRule sig)) :
    Tree sig → Prop where
  | fact {literal} : literal ∈ facts → Valid facts rules (.fact literal)
  | step {rule children} : rule ∈ rules →
      children.map conclusion = rule.premises →
      (∀ child ∈ children, Valid facts rules child) → Valid facts rules (.step rule children)

theorem soundness {facts : List (Literal sig)} {rules : List (GroundRule sig)}
    {tree : Tree sig} (valid : Valid facts rules tree) :
    Derivable facts rules tree.conclusion := by
  induction valid with
  | fact member => exact .assumption member
  | step member same _ ih =>
    apply Derivable.application member
    intro premise hp
    rw [← same] at hp
    obtain ⟨child, hc, eq⟩ := List.mem_map.mp hp
    subst premise
    exact ih child hc

private theorem collectTrees {facts : List (Literal sig)} {rules : List (GroundRule sig)}
    (premises : List (Literal sig))
    (available : ∀ premise ∈ premises,
      ∃ tree : Tree sig, Valid facts rules tree ∧ tree.conclusion = premise) :
    ∃ children : List (Tree sig), children.map conclusion = premises ∧
      ∀ child ∈ children, Valid facts rules child := by
  induction premises with
  | nil => exact ⟨[], rfl, fun _ member => by cases member⟩
  | cons premise rest ih =>
    obtain ⟨head, hh, same⟩ := available premise (by simp)
    obtain ⟨tail, matching, ht⟩ := ih (fun p hp => available p (List.mem_cons_of_mem _ hp))
    refine ⟨head :: tail, ?_, ?_⟩
    · simp only [List.map_cons, same, matching]
    · intro child member
      cases member with
      | head => exact hh
      | tail _ hm => exact ht child hm

-- This is existence in Prop. It does not eliminate a Prop proof into Type or
-- implement proof search. Callers must supply a tree for the executable checker.
theorem certificate_exists {facts : List (Literal sig)} {rules : List (GroundRule sig)}
    {literal : Literal sig} (proof : Derivable facts rules literal) :
    ∃ tree : Tree sig, Valid facts rules tree ∧ tree.conclusion = literal := by
  induction proof with
  | assumption member => exact ⟨.fact _, .fact member, rfl⟩
  | application member _ ih =>
    obtain ⟨children, matching, valid⟩ := collectTrees _ ih
    exact ⟨.step _ children, .step member matching valid, rfl⟩

theorem derivable_iff_certificate (facts : List (Literal sig))
    (rules : List (GroundRule sig)) (literal : Literal sig) :
    Derivable facts rules literal ↔
      ∃ tree : Tree sig, Valid facts rules tree ∧ tree.conclusion = literal :=
  ⟨certificate_exists, fun ⟨_, valid, same⟩ => same ▸ soundness valid⟩

theorem valid_uses_facts {facts : List (Literal sig)} {rules : List (GroundRule sig)}
    {tree : Tree sig} (valid : Valid facts rules tree) : tree.usedFacts ⊆ facts := by
  induction valid with
  | fact member =>
    intro literal used
    simp only [usedFacts, List.mem_singleton] at used
    exact used ▸ member
  | step _ _ _ ih =>
    intro literal used
    simp only [usedFacts] at used
    obtain ⟨child, hc, member⟩ := List.mem_flatMap.mp used
    exact ih child hc member

theorem valid_uses_rules {facts : List (Literal sig)} {rules : List (GroundRule sig)}
    {tree : Tree sig} (valid : Valid facts rules tree) : tree.usedRules ⊆ rules := by
  induction valid with
  | fact _ => intro _ used; simp [usedRules] at used
  | step member _ _ ih =>
    intro rule used
    simp only [usedRules] at used
    cases used with
    | head => exact member
    | tail _ hm =>
      obtain ⟨child, hc, hr⟩ := List.mem_flatMap.mp hm
      exact ih child hc hr

theorem preserve_support {facts newFacts : List (Literal sig)}
    {rules newRules : List (GroundRule sig)} {tree : Tree sig}
    (valid : Valid facts rules tree)
    (hf : tree.usedFacts ⊆ newFacts) (hr : tree.usedRules ⊆ newRules) :
    Valid newFacts newRules tree := by
  induction valid with
  | fact _ => exact .fact (hf (by simp [usedFacts]))
  | step _ matching _ ih =>
    simp only [usedFacts] at hf
    simp only [usedRules] at hr
    refine .step (hr (by simp)) matching ?_
    intro child hc
    apply ih child hc
    · intro literal used
      exact hf (List.mem_flatMap.mpr ⟨child, hc, used⟩)
    · intro rule used
      exact hr (List.mem_cons_of_mem _ (List.mem_flatMap.mpr ⟨child, hc, used⟩))

theorem derivable_of_preserved_support {facts newFacts : List (Literal sig)}
    {rules newRules : List (GroundRule sig)} {tree : Tree sig}
    (valid : Valid facts rules tree)
    (hf : tree.usedFacts ⊆ newFacts) (hr : tree.usedRules ⊆ newRules) :
    Derivable newFacts newRules tree.conclusion := soundness (preserve_support valid hf hr)

theorem valid_congr_membership {facts newFacts : List (Literal sig)}
    {rules newRules : List (GroundRule sig)} (tree : Tree sig)
    (hf : ∀ literal, literal ∈ facts ↔ literal ∈ newFacts)
    (hr : ∀ rule, rule ∈ rules ↔ rule ∈ newRules) :
    Valid facts rules tree ↔ Valid newFacts newRules tree := by
  constructor
  · intro valid
    exact preserve_support valid
      (fun _ used => (hf _).mp (valid_uses_facts valid used))
      (fun _ used => (hr _).mp (valid_uses_rules valid used))
  · intro valid
    exact preserve_support valid
      (fun _ used => (hf _).mpr (valid_uses_facts valid used))
      (fun _ used => (hr _).mpr (valid_uses_rules valid used))

instance groundRuleDecidableEq [DecidableEq (Literal sig)] : DecidableEq (GroundRule sig)
  | ⟨ps, c⟩, ⟨qs, d⟩ =>
      match decEq ps qs, decEq c d with
      | isTrue hp, isTrue hc => isTrue (by cases hp; cases hc; rfl)
      | isFalse different, _ =>
          isFalse (fun same => different (congrArg GroundRule.premises same))
      | _, isFalse different =>
          isFalse (fun same => different (congrArg GroundRule.conclusion same))

def check [DecidableEq (Literal sig)] (facts : List (Literal sig))
    (rules : List (GroundRule sig)) : Tree sig → Bool
  | .fact literal => decide (literal ∈ facts)
  | .step rule children => decide (rule ∈ rules) &&
      decide (children.map conclusion = rule.premises) &&
      children.attach.all (fun child => check facts rules child.val)
termination_by tree => sizeOf tree
decreasing_by
  have smaller := List.sizeOf_lt_of_mem child.property
  simp_wf
  omega

theorem check_iff_valid [DecidableEq (Literal sig)] (facts : List (Literal sig))
    (rules : List (GroundRule sig)) (tree : Tree sig) :
    check facts rules tree = true ↔ Valid facts rules tree := by
  induction tree using inductionTree with
  | factCase literal =>
    simp only [check, decide_eq_true_eq]
    exact ⟨Valid.fact, fun h => by cases h with | fact member => exact member⟩
  | stepCase rule children ih =>
    simp only [check, Bool.and_eq_true, decide_eq_true_eq, List.all_eq_true,
      List.mem_attach, forall_const, Subtype.forall]
    constructor
    · rintro ⟨⟨member, same⟩, checked⟩
      exact .step member same (fun child hc => (ih child hc).mp (checked child hc))
    · intro valid
      cases valid with
      | step member same validChildren =>
        exact ⟨⟨member, same⟩, fun child hc => (ih child hc).mpr (validChildren child hc)⟩

theorem reject_missing_fact [DecidableEq (Literal sig)]
    {facts : List (Literal sig)} {rules : List (GroundRule sig)} {tree : Tree sig}
    {literal : Literal sig} (used : literal ∈ tree.usedFacts) (missing : literal ∉ facts) :
    check facts rules tree = false := by
  cases checked : check facts rules tree with
  | false => rfl
  | true => exact False.elim (missing (valid_uses_facts ((check_iff_valid _ _ _).mp checked) used))

theorem reject_missing_rule [DecidableEq (Literal sig)]
    {facts : List (Literal sig)} {rules : List (GroundRule sig)} {tree : Tree sig}
    {rule : GroundRule sig} (used : rule ∈ tree.usedRules) (missing : rule ∉ rules) :
    check facts rules tree = false := by
  cases checked : check facts rules tree with
  | false => rfl
  | true => exact False.elim (missing (valid_uses_rules ((check_iff_valid _ _ _).mp checked) used))

def verify [DecidableEq (Literal sig)] (facts : List (Literal sig))
    (rules : List (GroundRule sig)) (expected : Literal sig) (tree : Tree sig) : Bool :=
  decide (tree.conclusion = expected) && check facts rules tree

theorem verify_iff [DecidableEq (Literal sig)] (facts : List (Literal sig))
    (rules : List (GroundRule sig)) (expected : Literal sig) (tree : Tree sig) :
    verify facts rules expected tree = true ↔
      tree.conclusion = expected ∧ Valid facts rules tree := by
  simp [verify, check_iff_valid]

theorem verify_sound [DecidableEq (Literal sig)] {facts : List (Literal sig)}
    {rules : List (GroundRule sig)} {expected : Literal sig} {tree : Tree sig}
    (accepted : verify facts rules expected tree = true) : Derivable facts rules expected := by
  obtain ⟨same, valid⟩ := (verify_iff facts rules expected tree).mp accepted
  exact same ▸ soundness valid

theorem derivable_iff_verified [DecidableEq (Literal sig)]
    (facts : List (Literal sig)) (rules : List (GroundRule sig)) (literal : Literal sig) :
    Derivable facts rules literal ↔ ∃ tree : Tree sig, verify facts rules literal tree = true := by
  constructor
  · intro proof
    obtain ⟨tree, valid, same⟩ := certificate_exists proof
    exact ⟨tree, (verify_iff facts rules literal tree).mpr ⟨same, valid⟩⟩
  · rintro ⟨_, accepted⟩
    exact verify_sound accepted

end Tree

-- R1's input lists remain representatives. This generic filter is proved to
-- mean exactly R2a set difference, for facts and (with equality) ground rules.
def remove {α : Type} [DecidableEq α] (values : List α) (removed : FiniteState α) : List α :=
  values.filter (fun value => !(removed.contains value))

@[simp] theorem mem_remove {α : Type} [DecidableEq α]
    (values : List α) (removed : FiniteState α) (value : α) :
    value ∈ remove values removed ↔ value ∈ values ∧ value ∉ removed := by
  simp only [remove, List.mem_filter]
  simp [Membership.mem]

theorem ofList_remove {α : Type} [DecidableEq α]
    (values : List α) (removed : FiniteState α) :
    FiniteState.ofList (remove values removed) = (FiniteState.ofList values).difference removed := by
  apply FiniteState.ext
  intro value
  simp

namespace Tree

variable {sig : Signature} [DecidableEq (Literal sig)]

theorem preserve_under_deletion {facts : List (Literal sig)}
    {rules : List (GroundRule sig)} {tree : Tree sig} (valid : Valid facts rules tree)
    (removedFacts : StateRelations sig) (removedRules : FiniteState (GroundRule sig))
    (hf : ∀ literal ∈ tree.usedFacts, literal ∉ removedFacts)
    (hr : ∀ rule ∈ tree.usedRules, rule ∉ removedRules) :
    Valid (remove facts removedFacts) (remove rules removedRules) tree :=
  preserve_support valid
    (fun literal used => (mem_remove _ _ _).mpr ⟨valid_uses_facts valid used, hf literal used⟩)
    (fun rule used => (mem_remove _ _ _).mpr ⟨valid_uses_rules valid used, hr rule used⟩)

theorem verify_after_deletion {facts : List (Literal sig)}
    {rules : List (GroundRule sig)} {expected : Literal sig} {tree : Tree sig}
    (accepted : verify facts rules expected tree = true)
    (removedFacts : StateRelations sig) (removedRules : FiniteState (GroundRule sig))
    (hf : ∀ literal ∈ tree.usedFacts, literal ∉ removedFacts)
    (hr : ∀ rule ∈ tree.usedRules, rule ∉ removedRules) :
    verify (remove facts removedFacts) (remove rules removedRules) expected tree = true := by
  obtain ⟨same, valid⟩ := (verify_iff facts rules expected tree).mp accepted
  exact (verify_iff _ _ _ tree).mpr
    ⟨same, preserve_under_deletion valid removedFacts removedRules hf hr⟩

end Tree

namespace Witness

-- Two explicit synthetic rules for the same subject. These are not legal
-- defaults: neither observation is a parking fact or a rule of responsibility.
inductive Predicate where
  | observationA | observationB | result
  deriving DecidableEq

def signature : Signature :=
  { SortId := Unit, Entity := fun _ => Nat, Predicate := Predicate,
    arity := fun _ => [()] }

private instance : DecidableEq signature.Predicate := inferInstanceAs (DecidableEq Predicate)
private instance : ∀ sort, DecidableEq (signature.Entity sort) :=
  fun _ => inferInstanceAs (DecidableEq Nat)

def atom (predicate : Predicate) : Atom signature := ⟨predicate, .cons (1 : Nat) .nil⟩
def a : Literal signature := (atom .observationA).positive
def b : Literal signature := (atom .observationB).positive
def result : Literal signature := (atom .result).positive
def fromA : GroundRule signature := ⟨[a], result⟩
def fromB : GroundRule signature := ⟨[b], result⟩
def facts := [a, b]
def rules := [fromA, fromB]
def aTree : Tree signature := .step fromA [.fact a]
def bTree : Tree signature := .step fromB [.fact b]

theorem independent_certificates :
    Tree.verify facts rules result aTree = true ∧
    Tree.verify facts rules result bTree = true := by
  simp [Tree.verify, Tree.check, Tree.conclusion, aTree, bTree]
  decide

theorem support_is_local :
    aTree.usedFacts = [a] ∧ aTree.usedRules = [fromA] ∧
    b ∉ aTree.usedFacts ∧ fromB ∉ aTree.usedRules := by
  simp [aTree, Tree.usedFacts, Tree.usedRules]
  decide

theorem malformed_children_rejected :
    Tree.verify facts rules result (.step fromA [.fact b]) = false ∧
    Tree.verify facts rules result (.step fromA []) = false ∧
    Tree.verify facts rules result (.step fromA [.fact a, .fact b]) = false := by
  simp [Tree.verify, Tree.check, Tree.conclusion, fromA]
  decide

theorem wrong_target_rejected :
    Tree.check facts rules aTree = true ∧ Tree.verify facts rules b aTree = false := by
  simp [Tree.verify, Tree.check, Tree.conclusion, aTree]
  decide

def withoutA := remove facts (FiniteState.ofList [a])
def rulesWithoutA := remove rules (FiniteState.ofList [fromA])

theorem alternate_after_fact_deletion :
    Tree.verify withoutA rules result aTree = false ∧
    Tree.verify withoutA rules result bTree = true ∧ Derivable withoutA rules result := by
  have checked : Tree.verify withoutA rules result aTree = false ∧
      Tree.verify withoutA rules result bTree = true := by
    simp [Tree.verify, Tree.check, Tree.conclusion, aTree, bTree, fromA, fromB]
    decide
  exact ⟨checked.1, checked.2, Tree.verify_sound checked.2⟩

theorem alternate_after_rule_deletion :
    Tree.verify facts rulesWithoutA result aTree = false ∧
    Tree.verify facts rulesWithoutA result bTree = true ∧ Derivable facts rulesWithoutA result := by
  have checked : Tree.verify facts rulesWithoutA result aTree = false ∧
      Tree.verify facts rulesWithoutA result bTree = true := by
    simp [Tree.verify, Tree.check, Tree.conclusion, aTree, bTree, fromA, fromB]
    decide
  exact ⟨checked.1, checked.2, Tree.verify_sound checked.2⟩

-- Instantiate preservation with nonempty removals of both facts and rules.
theorem unused_deletions_preserve_selected_tree :
    Tree.verify (remove facts (FiniteState.ofList [b]))
      (remove rules (FiniteState.ofList [fromB])) result aTree = true := by
  apply Tree.verify_after_deletion independent_certificates.1
  · intro literal used
    have same : aTree.usedFacts = [a] := support_is_local.1
    rw [same] at used
    simp only [List.mem_singleton] at used
    subst literal
    decide
  · intro rule used
    have same : aTree.usedRules = [fromA] := support_is_local.2.1
    rw [same] at used
    simp only [List.mem_singleton] at used
    subst rule
    decide

def withoutBoth := remove facts (FiniteState.ofList [a, b])

theorem no_result_without_both_bases : ¬ Derivable withoutBoth rules result := by
  have empty : withoutBoth = [] := by decide
  rw [empty]
  apply not_derivable_of_countermodel (fun _ => False) ?_ (fun h => h)
  constructor
  · intro _ member; cases member
  · intro rule member premises
    simp only [rules, List.mem_cons, List.not_mem_nil, or_false] at member
    rcases member with same | same
    · subst rule
      exact premises a (by simp [fromA])
    · subst rule
      exact premises b (by simp [fromB])

end Witness

end NormLabDerivationTraces
