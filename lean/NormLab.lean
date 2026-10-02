-- Trusted, finite synthetic profile. No user-provided Lean source is imported.
namespace NormLab

inductive Finding where
  | unreviewed | established | refuted | notEstablished
  deriving DecidableEq

inductive RuleStatus where
  | applied | inapplicable | unresolved
  deriving DecidableEq

structure Outcome where
  finding : Finding
  prisonMonths : Nat
  fineAmount : Nat
  ruleStatus : RuleStatus
  deriving DecidableEq

-- A relation stated independently of the TypeScript producer.
def Permissible (numerator denominator : Nat) (o : Outcome) : Prop :=
  o.fineAmount = 200000 ∧
  ((o.finding = .established ∧ o.prisonMonths * denominator = 120 * numerator ∧
    o.ruleStatus = .applied) ∨
   (o.finding = .refuted ∧ o.prisonMonths = 120 ∧ o.ruleStatus = .inapplicable))

instance (n d : Nat) (o : Outcome) : Decidable (Permissible n d o) :=
  inferInstanceAs (Decidable (_ ∧ _))

def ValidResult (state : Finding) (n d : Nat) (conditional : Bool)
    (ledger : RuleStatus) (outcomes : List Outcome) : Prop :=
  0 < n ∧ 0 < d ∧ n ≤ d ∧
  match state, outcomes with
  | .established, [o] => conditional = false ∧ ledger = .applied ∧
      o.finding = .established ∧ Permissible n d o
  | .refuted, [o] => conditional = false ∧ ledger = .inapplicable ∧
      o.finding = .refuted ∧ Permissible n d o
  | .unreviewed, [a, b] | .notEstablished, [a, b] =>
      conditional = true ∧ ledger = .unresolved ∧
      a.finding = .established ∧ b.finding = .refuted ∧
      Permissible n d a ∧ Permissible n d b
  | _, _ => False

instance (state : Finding) (n d : Nat) (conditional : Bool)
    (ledger : RuleStatus) (outcomes : List Outcome) :
    Decidable (ValidResult state n d conditional ledger outcomes) := by
  unfold ValidResult
  cases state <;> cases outcomes with
  | nil => exact inferInstance
  | cons a rest => cases rest with
    | nil => exact inferInstance
    | cons b rest => cases rest <;> exact inferInstance

-- Consequences are unique for a completed finding within each supported bundle.
theorem original_established_unique (o : Outcome)
    (h : Permissible 2 3 o) (hs : o.finding = .established) :
    o.prisonMonths = 80 ∧ o.fineAmount = 200000 := by
  obtain ⟨fine, h | h⟩ := h
  · constructor
    · have := h.2.1; omega
    · exact fine
  · have impossible := hs.symm.trans h.1
    cases impossible

theorem original_refuted_unique (o : Outcome)
    (h : Permissible 2 3 o) (hs : o.finding = .refuted) :
    o.prisonMonths = 120 ∧ o.fineAmount = 200000 := by
  obtain ⟨fine, h | h⟩ := h
  · have impossible := hs.symm.trans h.1
    cases impossible
  · exact ⟨h.2.1, fine⟩

theorem experimental_established_unique (o : Outcome)
    (h : Permissible 1 2 o) (hs : o.finding = .established) :
    o.prisonMonths = 60 ∧ o.fineAmount = 200000 := by
  obtain ⟨fine, h | h⟩ := h
  · constructor
    · have := h.2.1; omega
    · exact fine
  · have impossible := hs.symm.trans h.1
    cases impossible

end NormLab
