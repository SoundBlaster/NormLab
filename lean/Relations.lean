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

-- Derivability itself is a model; soundness makes it the least one pointwise.
-- This is a semantic construction, not an algorithm enumerating the closure.
def canonicalModel {sig : Signature} (facts : List (Literal sig))
    (rules : List (GroundRule sig)) : Interpretation sig := Derivable facts rules

theorem canonicalModel_models {sig : Signature} (facts : List (Literal sig))
    (rules : List (GroundRule sig)) : Models (canonicalModel facts rules) facts rules :=
  ⟨fun _ member => .assumption member,
   fun _ member premises => .application member premises⟩

theorem canonicalModel_least {sig : Signature} {facts : List (Literal sig)}
    {rules : List (GroundRule sig)} (model : Interpretation sig)
    (hm : Models model facts rules) :
    ∀ literal, canonicalModel facts rules literal → model literal :=
  fun _ proof => soundness model hm proof

def SemanticConsequence {sig : Signature} (facts : List (Literal sig))
    (rules : List (GroundRule sig)) (literal : Literal sig) : Prop :=
  ∀ model, Models model facts rules → model literal

theorem completeness {sig : Signature} {facts : List (Literal sig)}
    {rules : List (GroundRule sig)} {literal : Literal sig}
    (h : SemanticConsequence facts rules literal) : Derivable facts rules literal :=
  h (canonicalModel facts rules) (canonicalModel_models facts rules)

theorem derivable_iff_semantic_consequence {sig : Signature}
    (facts : List (Literal sig)) (rules : List (GroundRule sig)) (literal : Literal sig) :
    Derivable facts rules literal ↔ SemanticConsequence facts rules literal :=
  ⟨fun proof model hm => soundness model hm proof, completeness⟩

-- The forward direction constructs the canonical countermodel directly;
-- no excluded middle, choice, or decidability of derivability is needed.
theorem not_derivable_iff_countermodel {sig : Signature}
    (facts : List (Literal sig)) (rules : List (GroundRule sig)) (literal : Literal sig) :
    ¬ Derivable facts rules literal ↔
      ∃ model, Models model facts rules ∧ ¬ model literal :=
  ⟨fun rejected => ⟨canonicalModel facts rules, canonicalModel_models facts rules, rejected⟩,
   fun ⟨model, hm, rejected⟩ => not_derivable_of_countermodel model hm rejected⟩

-- Inclusion is propositional List membership; no equality decision procedure.
theorem monotonicity {sig : Signature}
    {facts largerFacts : List (Literal sig)} {rules largerRules : List (GroundRule sig)}
    (hf : facts ⊆ largerFacts) (hr : rules ⊆ largerRules) {literal : Literal sig}
    (h : Derivable facts rules literal) : Derivable largerFacts largerRules literal := by
  induction h with
  | assumption member => exact .assumption (hf member)
  | application member _ ih => exact .application (hr member) ih

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

namespace DutyClaim

-- Entity types may be infinite and need no DecidableEq instance. Only the
-- supplied ground triples are materialized as facts and matching rules.
inductive SortId where
  | person | authority | episode
inductive Predicate where
  | duty | claim
structure Triple (Person Authority Episode : Type) where
  person : Person
  authority : Authority
  episode : Episode

def Entity (Person Authority Episode : Type) : SortId → Type
  | .person => Person
  | .authority => Authority
  | .episode => Episode
def signature (Person Authority Episode : Type) : Signature :=
  { SortId := SortId, Entity := Entity Person Authority Episode, Predicate := Predicate
    arity := fun
      | .duty => [.person, .authority, .episode]
      | .claim => [.authority, .person, .episode] }

variable {Person Authority Episode : Type}

def duty (person : Person) (authority : Authority) (episode : Episode) :
    Atom (signature Person Authority Episode) :=
  ⟨.duty, .cons person (.cons authority (.cons episode .nil))⟩
def claim (authority : Authority) (person : Person) (episode : Episode) :
    Atom (signature Person Authority Episode) :=
  ⟨.claim, .cons authority (.cons person (.cons episode .nil))⟩
def dutyToClaim (triple : Triple Person Authority Episode) :
    GroundRule (signature Person Authority Episode) :=
  ⟨[(duty triple.person triple.authority triple.episode).positive],
   (claim triple.authority triple.person triple.episode).positive⟩
def facts (triples : List (Triple Person Authority Episode)) :=
  triples.map fun t => (duty t.person t.authority t.episode).positive
def rules (triples : List (Triple Person Authority Episode)) := triples.map dutyToClaim

private theorem mapped_member {α β : Type} (f : α → β) (values : List α) (value : β)
    (member : value ∈ values.map f) : ∃ x ∈ values, f x = value := by
  induction values with
  | nil => cases member
  | cons x rest ih =>
    cases member with
    | head => exact ⟨x, .head rest, rfl⟩
    | tail _ hm =>
      obtain ⟨y, hy, same⟩ := ih hm
      exact ⟨y, .tail x hy, same⟩

private theorem member_mapped {α β : Type} (f : α → β) {values : List α} {x : α}
    (member : x ∈ values) : f x ∈ values.map f := by
  induction member with
  | head => exact .head _
  | tail _ _ ih => exact .tail _ ih

-- Both predicates keep the exact ordered triple. This interpretation rejects
-- every claim whose person, authority, or episode has no matching input duty.
def imageModel (triples : List (Triple Person Authority Episode)) :
    Interpretation (signature Person Authority Episode)
  | ⟨.positive, ⟨.duty, .cons person (.cons authority (.cons episode .nil))⟩⟩ =>
      Triple.mk person authority episode ∈ triples
  | ⟨.positive, ⟨.claim, .cons authority (.cons person (.cons episode .nil))⟩⟩ =>
      Triple.mk person authority episode ∈ triples
  | ⟨.negative, _⟩ => False

theorem imageModel_models (triples : List (Triple Person Authority Episode)) :
    Models (imageModel triples) (facts triples) (rules triples) := by
  constructor
  · intro literal member
    obtain ⟨triple, found, same⟩ := mapped_member _ triples literal member
    subst literal
    exact found
  · intro rule member premises
    obtain ⟨triple, _, same⟩ := mapped_member _ triples rule member
    subst rule
    exact premises (duty triple.person triple.authority triple.episode).positive
      (List.Mem.head [])

-- The assumptions are explicit in `facts`/`rules`: only positive input duties
-- and exactly their dutyToClaim instances. Additional rules need a new proof.
theorem claim_derivable_iff_mem (triples : List (Triple Person Authority Episode))
    (person : Person) (authority : Authority) (episode : Episode) :
    Derivable (facts triples) (rules triples) (claim authority person episode).positive ↔
      Triple.mk person authority episode ∈ triples := by
  constructor
  · exact soundness (imageModel triples) (imageModel_models triples)
  · intro member
    apply Derivable.application (rule := dutyToClaim ⟨person, authority, episode⟩)
      (member_mapped dutyToClaim member)
    intro premise inPremises
    cases inPremises with
    | head => exact .assumption (member_mapped _ member)
    | tail _ impossible => cases impossible

end DutyClaim

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
#print axioms canonicalModel_models
#print axioms canonicalModel_least
#print axioms completeness
#print axioms derivable_iff_semantic_consequence
#print axioms not_derivable_iff_countermodel
#print axioms monotonicity
#print axioms derivable_without_rules_iff
#print axioms opposed_support_without_explosion
#print axioms DutyClaim.imageModel_models
#print axioms DutyClaim.claim_derivable_iff_mem
#print axioms Example.supported_claim
#print axioms Example.countermodel_nonempty
#print axioms Example.countermodel_models
#print axioms Example.wrong_person_not_derivable
#print axioms Example.wrong_episode_not_derivable
#print axioms Example.missing_support_is_not_negative
#print axioms Example.conflicting_duty_without_claim

end NormLabRelations
