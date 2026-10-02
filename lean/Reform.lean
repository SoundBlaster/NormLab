-- Independent relation for the bounded reform profile. No producer code or user source.
namespace NormLabReform

inductive Group where
  | K1 | K2
  deriving DecidableEq
inductive Finding where
  | unreviewed | established | refuted | notEstablished
  deriving DecidableEq
inductive Trigger where
  | M | N
  deriving DecidableEq
inductive Status where
  | applied | inapplicable | excluded | unresolved
  deriving DecidableEq
inductive Operation where
  | baseline (months fine : Nat)
  | scale (trigger : Trigger) (numerator denominator : Nat)
  | exclude
  deriving DecidableEq
structure Rule where
  id : Nat
  groups : List Group
  operation : Operation
  deriving DecidableEq
structure Input where
  group : Group
  M : Bool
  N : Bool
  E : Bool
  deriving DecidableEq
structure Snapshot where
  group : Group
  M : Finding
  N : Finding
  E : Finding
  deriving DecidableEq
structure Outcome where
  qualification : Group
  months : Nat
  fine : Nat
  deriving DecidableEq
structure Entry where
  rule : Nat
  status : Status
  excludedBy : Option Nat
  deriving DecidableEq
structure Step where
  rule : Nat
  beforeMonths : Nat
  afterMonths : Nat
  deriving DecidableEq
structure Branch where
  input : Input
  outcome : Outcome
  ledger : List Entry
  steps : List Step
  deriving DecidableEq
structure Result where
  conditional : Bool
  branches : List Branch
  ledger : List Entry
  deriving DecidableEq
structure Parameters where
  baseId : Nat
  base : Nat
  fine : Nat
  mId : Nat
  mNum : Nat
  mDen : Nat
  nId : Nat
  nNum : Nat
  nDen : Nat
  exclusionId : Nat
  deriving DecidableEq

def domain : List Input :=
  [Group.K1, .K2].flatMap fun g => [false, true].flatMap fun m =>
    [false, true].flatMap fun n => [false, true].map fun e => ⟨g, m, n, e⟩

theorem domain_cardinality : domain.length = 16 := by decide +kernel
theorem domain_distinct : domain.Nodup := by decide +kernel
theorem domain_complete (x : Input) : x ∈ domain := by
  cases x with
  | mk g m n e => cases g <;> cases m <;> cases n <;> cases e <;> decide +kernel

def compatible (state : Finding) (value : Bool) : Bool :=
  match state with
  | .established => value
  | .refuted => !value
  | .unreviewed | .notEstablished => true
def terminal (state : Finding) : Bool :=
  state == .established || state == .refuted
def completions (s : Snapshot) : List Input :=
  domain.filter fun x => x.group == s.group && compatible s.M x.M &&
    compatible s.N x.N && compatible s.E x.E

-- Resolve by operation and scope, independently checking exactly one of every obligation.
def select (rules : List Rule) (group : Group) : Option Parameters :=
  let matching := rules.filter fun r => r.groups.contains group
  let bases := matching.filterMap fun r => match r.operation with
    | .baseline b f => some (r.id, b, f)
    | _ => none
  let ms := matching.filterMap fun r => match r.operation with
    | .scale .M n d => some (r.id, n, d)
    | _ => none
  let ns := matching.filterMap fun r => match r.operation with
    | .scale .N n d => some (r.id, n, d)
    | _ => none
  let exclusions := matching.filterMap fun r => match r.operation with
    | .exclude => some r.id
    | _ => none
  match bases, ms, ns, exclusions with
  | [(b, months, fine)], [(m, mn, md)], [(n, nn, nd)], [e] =>
      some ⟨b, months, fine, m, mn, md, n, nn, nd, e⟩
  | _, _, _, _ => none

def nEligible (x : Input) : Bool := x.N && !x.E
def afterM (p : Parameters) (x : Input) : Nat :=
  if x.M then p.base * p.mNum / p.mDen else p.base
def nDenominator (p : Parameters) (x : Input) : Nat :=
  if nEligible x then p.nDen else 1
def nNumerator (p : Parameters) (x : Input) : Nat :=
  if nEligible x then p.nNum else 1

-- Exact equations, with no rounded or silently omitted intermediate consequence.
def Permissible (p : Parameters) (x : Input) (y : Outcome) : Prop :=
  y.qualification = x.group ∧ y.fine = p.fine ∧
  (if x.M then afterM p x * p.mDen = p.base * p.mNum else True) ∧
  y.months * nDenominator p x = afterM p x * nNumerator p x
instance (p : Parameters) (x : Input) (y : Outcome) : Decidable (Permissible p x y) :=
  inferInstanceAs (Decidable (_ ∧ _))
def canonicalOutcome (p : Parameters) (x : Input) : Outcome :=
  ⟨x.group, afterM p x * nNumerator p x / nDenominator p x, p.fine⟩

def ModelPermissible (rules : List Rule) (x : Input) (y : Outcome) : Prop :=
  match select rules x.group with
  | some p => Permissible p x y
  | none => False
instance (rules : List Rule) (x : Input) (y : Outcome) :
    Decidable (ModelPermissible rules x y) := by
  unfold ModelPermissible
  split <;> infer_instance

def ValidParameters (p : Parameters) : Prop :=
  0 < p.mNum ∧ p.mNum ≤ p.mDen ∧ p.mDen ≤ 12 ∧
  0 < p.nNum ∧ p.nNum ≤ p.nDen ∧ p.nDen ≤ 12 ∧
  p.base ≤ 3600 ∧ p.fine ≤ 1000000
instance (p : Parameters) : Decidable (ValidParameters p) :=
  inferInstanceAs (Decidable (_ ∧ _))

def SupportedInput (rules : List Rule) (x : Input) : Prop :=
  match select rules x.group with
  | some p => ValidParameters p ∧ Permissible p x (canonicalOutcome p x)
  | none => False
instance (rules : List Rule) (x : Input) : Decidable (SupportedInput rules x) := by
  unfold SupportedInput
  split <;> infer_instance

def WellFormed (rules : List Rule) : Prop :=
  rules.length ≥ 4 ∧ rules.length ≤ 12 ∧
  rules.map Rule.id = List.range rules.length ∧
  (∀ r ∈ rules, r.groups ≠ [] ∧ r.groups.Nodup) ∧
  (∀ x ∈ domain, SupportedInput rules x)
instance (rules : List Rule) : Decidable (WellFormed rules) :=
  inferInstanceAs (Decidable (_ ∧ _))

def prescription (rules : List Rule) (p : Parameters) (x : Input) : List Entry :=
  rules.map fun r =>
    if !r.groups.contains x.group then ⟨r.id, .inapplicable, none⟩ else
    match r.operation with
    | .baseline _ _ => ⟨r.id, .applied, none⟩
    | .exclude => ⟨r.id, if x.N && x.E then .applied else .inapplicable, none⟩
    | .scale .M _ _ => ⟨r.id, if x.M then .applied else .inapplicable, none⟩
    | .scale .N _ _ =>
        if !x.N then ⟨r.id, .inapplicable, none⟩ else
        if x.E then ⟨r.id, .excluded, some p.exclusionId⟩ else ⟨r.id, .applied, none⟩

def requiredSteps (p : Parameters) (x : Input) : List Step :=
  (if x.M then [⟨p.mId, p.base, afterM p x⟩] else []) ++
  (if nEligible x then
    [⟨p.nId, afterM p x, (canonicalOutcome p x).months⟩] else [])

def BranchPermissible (rules : List Rule) (b : Branch) : Prop :=
  match select rules b.input.group with
  | some p => Permissible p b.input b.outcome ∧
      b.ledger = prescription rules p b.input ∧ b.steps = requiredSteps p b.input
  | none => False
instance (rules : List Rule) (b : Branch) : Decidable (BranchPermissible rules b) := by
  unfold BranchPermissible
  split <;> infer_instance

def prescribedLedger (rules : List Rule) (x : Input) : List Entry :=
  match select rules x.group with
  | some p => prescription rules p x
  | none => []
def summary (rules : List Rule) (s : Snapshot) : List Entry :=
  rules.map fun r =>
    let entries := (completions s).filterMap fun x =>
      (prescribedLedger rules x).find? fun e => e.rule == r.id
    match entries with
    | [] => ⟨r.id, .unresolved, none⟩
    | first :: rest => if rest.all (· == first) then first else ⟨r.id, .unresolved, none⟩

def ValidCandidate (rules : List Rule) (s : Snapshot) (result : Result) : Prop :=
  result.conditional = !(terminal s.M && terminal s.N && terminal s.E) ∧
  result.branches.map Branch.input = completions s ∧
  (∀ b ∈ result.branches, BranchPermissible rules b) ∧
  result.ledger = summary rules s
instance (rules : List Rule) (s : Snapshot) (result : Result) :
    Decidable (ValidCandidate rules s result) :=
  inferInstanceAs (Decidable (_ ∧ _))
def ValidResult (rules : List Rule) (s : Snapshot) (result : Result) : Prop :=
  WellFormed rules ∧ ValidCandidate rules s result
instance (rules : List Rule) (s : Snapshot) (result : Result) :
    Decidable (ValidResult rules s result) :=
  inferInstanceAs (Decidable (_ ∧ _))

-- Uniqueness is a general theorem about the relation, not enumeration of candidate values.
theorem permissible_unique (p : Parameters) (x : Input) (a b : Outcome)
    (hp : ValidParameters p) (ha : Permissible p x a) (hb : Permissible p x b) : a = b := by
  have hd : 0 < nDenominator p x := by
    unfold nDenominator
    split
    · exact Nat.lt_of_lt_of_le hp.2.2.2.1 hp.2.2.2.2.1
    · decide
  have hm : a.months = b.months := Nat.eq_of_mul_eq_mul_right hd (ha.2.2.2.trans hb.2.2.2.symm)
  have hg := ha.1.trans hb.1.symm
  have hf := ha.2.1.trans hb.2.1.symm
  cases a; cases b; simp_all

theorem model_exists_unique (rules : List Rule) (h : WellFormed rules)
    (x : Input) (hx : x ∈ domain) :
    ∃ y, ModelPermissible rules x y ∧ ∀ z, ModelPermissible rules x z → z = y := by
  have support := h.2.2.2.2 x hx
  unfold SupportedInput at support
  cases selected : select rules x.group with
  | none => simp [selected] at support
  | some p =>
    simp only [selected] at support
    refine ⟨canonicalOutcome p x, ?_, ?_⟩
    · simpa [ModelPermissible, selected] using support.2
    · intro z hz
      simp only [ModelPermissible, selected] at hz
      exact permissible_unique p x z (canonicalOutcome p x) support.1 hz support.2

theorem result_sound (rules : List Rule) (s : Snapshot) (r : Result)
    (h : ValidResult rules s r) (b : Branch) (hb : b ∈ r.branches) :
    ModelPermissible rules b.input b.outcome := by
  have valid := h.2.2.2.1 b hb
  unfold BranchPermissible at valid
  unfold ModelPermissible
  split at valid <;> simp_all

theorem result_complete (rules : List Rule) (s : Snapshot) (r : Result)
    (h : ValidResult rules s r) : r.branches.map Branch.input = completions s := h.2.2.1

-- Every permissible outcome of every compatible completion is represented.
private theorem represented (branches : List Branch) (x : Input)
    (h : x ∈ branches.map Branch.input) : ∃ b ∈ branches, b.input = x := by
  induction branches with
  | nil => cases h
  | cons b rest ih =>
    cases h with
    | head => exact ⟨b, List.Mem.head rest, rfl⟩
    | tail _ ht =>
      obtain ⟨value, member, same⟩ := ih ht
      exact ⟨value, List.Mem.tail b member, same⟩

theorem outcome_complete (rules : List Rule) (s : Snapshot) (r : Result)
    (h : ValidResult rules s r) (x : Input) (hx : x ∈ completions s)
    (y : Outcome) (hy : ModelPermissible rules x y) :
    ∃ b ∈ r.branches, b.input = x ∧ b.outcome = y := by
  have covered : x ∈ r.branches.map Branch.input := by
    rw [result_complete rules s r h]
    exact hx
  obtain ⟨b, hb, same⟩ := represented r.branches x covered
  have inDomain : x ∈ domain := (List.mem_filter.mp hx).1
  obtain ⟨value, _, unique⟩ := model_exists_unique rules h.1 x inDomain
  have permissible := result_sound rules s r h b hb
  rw [same] at permissible
  exact ⟨b, hb, same, (unique b.outcome permissible).trans (unique y hy).symm⟩

theorem mandatory_complete (rules : List Rule) (s : Snapshot) (r : Result)
    (h : ValidResult rules s r) (b : Branch) (hb : b ∈ r.branches) (p : Parameters)
    (hp : select rules b.input.group = some p) :
    b.ledger = prescription rules p b.input ∧ b.steps = requiredSteps p b.input := by
  have valid := h.2.2.2.1 b hb
  simp only [BranchPermissible, hp] at valid
  exact valid.2

end NormLabReform
