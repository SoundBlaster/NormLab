-- Bounded relation core: typed ground literals and explicit ground Horn rules.
-- No runtime adapter, variables, unification, search, or legal defaults are defined.
namespace NormLabRelations

structure Signature where
  SortId : Type
  Entity : SortId → Type
  Predicate : Type
  arity : Predicate → List SortId

-- The signature fixes both the number and the sort of every argument.
inductive Args (sig : Signature) : List sig.SortId → Type where
  | nil : Args sig []
  | cons {sort : sig.SortId} {rest : List sig.SortId} :
      sig.Entity sort → Args sig rest → Args sig (sort :: rest)

structure Atom (sig : Signature) where
  predicate : sig.Predicate
  args : Args sig (sig.arity predicate)

inductive Polarity where
  | positive | negative
  deriving DecidableEq

-- Negative support is data, not Lean's logical negation of positive support.
structure Literal (sig : Signature) where
  polarity : Polarity
  atom : Atom sig

def Atom.positive {sig : Signature} (atom : Atom sig) : Literal sig :=
  ⟨.positive, atom⟩
def Atom.negative {sig : Signature} (atom : Atom sig) : Literal sig :=
  ⟨.negative, atom⟩

-- Each rule is already ground. A Lean function constructing rules is not a DSL
-- quantifier: only the instances explicitly included in `rules` can be applied.
structure GroundRule (sig : Signature) where
  premises : List (Literal sig)
  conclusion : Literal sig

inductive Derivable {sig : Signature}
    (facts : List (Literal sig)) (rules : List (GroundRule sig)) : Literal sig → Prop where
  | assumption {literal} : literal ∈ facts → Derivable facts rules literal
  | application {rule} : rule ∈ rules →
      (∀ premise ∈ rule.premises, Derivable facts rules premise) →
      Derivable facts rules rule.conclusion

abbrev Interpretation (sig : Signature) := Literal sig → Prop

def ModelsFacts {sig : Signature} (model : Interpretation sig)
    (facts : List (Literal sig)) : Prop := ∀ literal ∈ facts, model literal
def ModelsRules {sig : Signature} (model : Interpretation sig)
    (rules : List (GroundRule sig)) : Prop :=
  ∀ rule ∈ rules, (∀ premise ∈ rule.premises, model premise) → model rule.conclusion
def Models {sig : Signature} (model : Interpretation sig)
    (facts : List (Literal sig)) (rules : List (GroundRule sig)) : Prop :=
  ModelsFacts model facts ∧ ModelsRules model rules

-- Soundness is relative to the explicitly supplied facts, rules, and model.
-- It establishes neither their real-world truth nor a complete legal theory.
theorem soundness {sig : Signature} {facts : List (Literal sig)}
    {rules : List (GroundRule sig)} {literal : Literal sig}
    (model : Interpretation sig) (hm : Models model facts rules)
    (h : Derivable facts rules literal) : model literal := by
  induction h with
  | assumption member => exact hm.1 _ member
  | application member _ ih => exact hm.2 _ member ih

theorem not_derivable_of_countermodel {sig : Signature}
    {facts : List (Literal sig)} {rules : List (GroundRule sig)} {literal : Literal sig}
    (model : Interpretation sig) (hm : Models model facts rules)
    (rejected : ¬ model literal) : ¬ Derivable facts rules literal :=
  fun proof => rejected (soundness model hm proof)

theorem derivable_without_rules_iff {sig : Signature}
    (facts : List (Literal sig)) (literal : Literal sig) :
    Derivable facts [] literal ↔ literal ∈ facts := by
  constructor
  · intro proof
    cases proof with
    | assumption member => exact member
    | application member _ => cases member
  · exact Derivable.assumption

-- Opposed evidence adds two facts; it introduces no explosion inference rule.
theorem opposed_support_without_explosion {sig : Signature} (a b : Atom sig)
    (different : b ≠ a) :
    Derivable [a.positive, a.negative] [] a.positive ∧
    Derivable [a.positive, a.negative] [] a.negative ∧
    ¬ Derivable [a.positive, a.negative] [] b.positive := by
  refine ⟨.assumption (by simp), .assumption (by simp), ?_⟩
  intro proof
  have member := (derivable_without_rules_iff _ _).mp proof
  simp only [List.mem_cons, List.not_mem_nil, or_false] at member
  rcases member with same | opposed
  · exact different (congrArg Literal.atom same)
  · have impossible := congrArg Literal.polarity opposed
    cases impossible

namespace Example

inductive SortId where
  | person | authority | episode
inductive Person where
  | alice | bob
  deriving DecidableEq
inductive Authority where
  | office
  deriving DecidableEq
inductive Episode where
  | first | second
  deriving DecidableEq
inductive Predicate where
  | duty | claim

def Entity : SortId → Type
  | .person => Person
  | .authority => Authority
  | .episode => Episode
def signature : Signature :=
  { SortId := SortId, Entity := Entity, Predicate := Predicate
    arity := fun
      | .duty => [.person, .authority, .episode]
      | .claim => [.authority, .person, .episode] }

def duty (person : Person) (authority : Authority) (episode : Episode) : Atom signature :=
  ⟨.duty, .cons person (.cons authority (.cons episode .nil))⟩
def claim (authority : Authority) (person : Person) (episode : Episode) : Atom signature :=
  ⟨.claim, .cons authority (.cons person (.cons episode .nil))⟩

-- Synthetic, explicitly chosen correlation; not a universal deontic axiom.
-- Identity and episode are preserved in the conclusion, while argument roles differ.
def dutyToClaim (person : Person) (authority : Authority) (episode : Episode) :
    GroundRule signature :=
  ⟨[(duty person authority episode).positive], (claim authority person episode).positive⟩
def facts : List (Literal signature) := [(duty .alice .office .first).positive]
def rules : List (GroundRule signature) := [dutyToClaim .alice .office .first]

theorem supported_claim : Derivable facts rules (claim .office .alice .first).positive := by
  apply Derivable.application (rule := dutyToClaim .alice .office .first) (by simp [rules])
  intro premise member
  simp only [dutyToClaim, List.mem_cons, List.not_mem_nil, or_false] at member
  subst premise
  exact .assumption (by simp [facts])

-- A concrete nonempty interpretation: the first episode supports Alice's duty
-- and the corresponding claim; no negative support is assigned. Entity sorts
-- are inhabited. No interpretation condition identifies negative with `¬`.
def countermodel : Interpretation signature
  | ⟨.positive, ⟨.duty, .cons person (.cons _ (.cons episode .nil))⟩⟩ =>
      person = .alice ∧ episode = .first
  | ⟨.positive, ⟨.claim, .cons _ (.cons person (.cons episode .nil))⟩⟩ =>
      person = .alice ∧ episode = .first
  | ⟨.negative, _⟩ => False

theorem countermodel_nonempty : ∃ literal, countermodel literal :=
  ⟨(duty .alice .office .first).positive, rfl, rfl⟩

theorem countermodel_models : Models countermodel facts rules := by
  constructor
  · intro literal member
    simp only [facts, List.mem_cons, List.not_mem_nil, or_false] at member
    subst literal
    exact ⟨rfl, rfl⟩
  · intro rule member premises
    simp only [rules, List.mem_cons, List.not_mem_nil, or_false] at member
    subst rule
    exact premises (duty .alice .office .first).positive (by simp [dutyToClaim])

theorem wrong_person_not_derivable :
    ¬ Derivable facts rules (claim .office .bob .first).positive := by
  apply not_derivable_of_countermodel countermodel countermodel_models
  intro holds
  cases holds.1

theorem wrong_episode_not_derivable :
    ¬ Derivable facts rules (claim .office .alice .second).positive := by
  apply not_derivable_of_countermodel countermodel countermodel_models
  intro holds
  cases holds.2

-- Neither polarity is supported for Bob. Failure to derive positive evidence
-- does not manufacture negative evidence (no closed-world rule is provided).
theorem missing_support_is_not_negative :
    ¬ Derivable facts rules (claim .office .bob .first).positive ∧
    ¬ Derivable facts rules (claim .office .bob .first).negative := by
  refine ⟨wrong_person_not_derivable, ?_⟩
  exact not_derivable_of_countermodel countermodel countermodel_models (fun h => h)

-- This demonstrates independent support only, not full Belnap/FDE semantics.
theorem conflicting_duty_without_claim :
    Derivable [(duty .alice .office .first).positive, (duty .alice .office .first).negative]
      [] (duty .alice .office .first).positive ∧
    Derivable [(duty .alice .office .first).positive, (duty .alice .office .first).negative]
      [] (duty .alice .office .first).negative ∧
    ¬ Derivable [(duty .alice .office .first).positive, (duty .alice .office .first).negative]
      [] (claim .office .alice .first).positive := by
  apply opposed_support_without_explosion
  intro same
  have impossible := congrArg Atom.predicate same
  cases impossible

end Example

-- Audit output is captured by the standalone Lean compile; no custom axioms.
#print axioms soundness
#print axioms not_derivable_of_countermodel
#print axioms derivable_without_rules_iff
#print axioms opposed_support_without_explosion
#print axioms Example.supported_claim
#print axioms Example.countermodel_nonempty
#print axioms Example.countermodel_models
#print axioms Example.wrong_person_not_derivable
#print axioms Example.wrong_episode_not_derivable
#print axioms Example.missing_support_is_not_negative
#print axioms Example.conflicting_duty_without_claim

end NormLabRelations
