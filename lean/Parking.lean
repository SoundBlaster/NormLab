-- Independent, bounded PoC profile; it does not determine real-world liability.
namespace NormLabParking

inductive Finding where
  | unreviewed | established | refuted | notEstablished | conflict
  deriving DecidableEq
inductive Condition where
  | inMoscow | cityParking | placement | paidRegime | personalCar
  | simplePayment | noPrivilege | noSpecialCircumstances | noPayment
  deriving DecidableEq
inductive Coordinate where
  | vehicle | participant | eventDate | location | timeInterval
  deriving DecidableEq
inductive Missing where
  | condition (id : Condition) | coordinate (id : Coordinate)
  deriving DecidableEq
inductive Outcome where
  | conflict | unsupported | incomplete | fragmentRefuted | fragmentMatched
  deriving DecidableEq
inductive Comparison where
  | notMentioned | notComputable | draftMatch | draftDifference
  deriving DecidableEq
structure Input where
  finding : Condition → Finding
  present : Coordinate → Bool
  claimedFine : Option Nat
structure Branch where
  condition : Condition
  assumption : Finding
  outcome : Outcome
  deriving DecidableEq
structure Result where
  outcome : Outcome
  conflicts : List Condition
  unsupported : List Condition
  refuted : List Condition
  missing : List Missing
  candidateFine : Option Nat
  comparison : Comparison
  branches : List Branch

def conditions : List Condition :=
  [.inMoscow, .cityParking, .placement, .paidRegime, .personalCar,
   .simplePayment, .noPrivilege, .noSpecialCircumstances, .noPayment]
def coordinates : List Coordinate :=
  [.vehicle, .participant, .eventDate, .location, .timeInterval]
def isScope : Condition → Bool
  | .placement | .paidRegime | .noPayment => false
  | _ => true
def conflicts (i : Input) : List Condition :=
  conditions.filter fun c => i.finding c == .conflict
def unsupported (i : Input) : List Condition :=
  conditions.filter fun c => isScope c && i.finding c == .refuted
def refuted (i : Input) : List Condition :=
  conditions.filter fun c => !isScope c && i.finding c == .refuted
def missing (i : Input) : List Missing :=
  (conditions.filter (fun c => i.finding c == .unreviewed || i.finding c == .notEstablished)).map Missing.condition ++
  ((coordinates.filter fun c => !i.present c).map Missing.coordinate)

-- Mutually exclusive admissibility clauses, independent of the TS producer.
def AllowedOutcome (i : Input) : Outcome → Prop
  | .conflict => conflicts i ≠ []
  | .unsupported => conflicts i = [] ∧ unsupported i ≠ []
  | .incomplete => conflicts i = [] ∧ unsupported i = [] ∧ missing i ≠ []
  | .fragmentRefuted => conflicts i = [] ∧ unsupported i = [] ∧ missing i = [] ∧ refuted i ≠ []
  | .fragmentMatched => conflicts i = [] ∧ unsupported i = [] ∧ missing i = [] ∧ refuted i = []
instance (i : Input) (o : Outcome) : Decidable (AllowedOutcome i o) := by
  cases o <;> unfold AllowedOutcome <;> infer_instance

def fine (o : Outcome) : Option Nat :=
  if o == .fragmentMatched then some 5000 else none
def comparison (i : Input) (o : Outcome) : Comparison :=
  match i.claimedFine, fine o with
  | none, _ => .notMentioned
  | some _, none => .notComputable
  | some a, some b => if a == b then .draftMatch else .draftDifference
def branches (i : Input) (o : Outcome) : List Branch :=
  match o, missing i with
  | .incomplete, [.condition c] =>
    [⟨c, .established, if (refuted i).isEmpty then .fragmentMatched else .fragmentRefuted⟩,
     ⟨c, .refuted, if isScope c then .unsupported else .fragmentRefuted⟩]
  | _, _ => []

def ValidResult (i : Input) (r : Result) : Prop :=
  r.conflicts = conflicts i ∧ r.unsupported = unsupported i ∧
  r.refuted = refuted i ∧ r.missing = missing i ∧
  AllowedOutcome i r.outcome ∧ r.candidateFine = fine r.outcome ∧
  r.comparison = comparison i r.outcome ∧ r.branches = branches i r.outcome
instance (i : Input) (r : Result) : Decidable (ValidResult i r) :=
  inferInstanceAs (Decidable (_ ∧ _))

theorem conflict_blocks (i : Input) (r : Result) (h : ValidResult i r)
    (hc : conflicts i ≠ []) : r.outcome = .conflict := by
  have ho := h.2.2.2.2.1
  cases he : r.outcome <;> simp_all [AllowedOutcome]

theorem unsupported_blocks (i : Input) (r : Result) (h : ValidResult i r)
    (hc : conflicts i = []) (hu : unsupported i ≠ []) : r.outcome = .unsupported := by
  have ho := h.2.2.2.2.1
  cases he : r.outcome <;> simp_all [AllowedOutcome]

theorem matched_requires_complete (i : Input) (r : Result) (h : ValidResult i r)
    (ho : r.outcome = .fragmentMatched) : missing i = [] := by
  have ha := h.2.2.2.2.1
  simp only [ho, AllowedOutcome] at ha
  exact ha.2.2.1

theorem fine_only_when_matched (i : Input) (r : Result) (h : ValidResult i r) :
    r.candidateFine = some 5000 ↔ r.outcome = .fragmentMatched := by
  rw [h.2.2.2.2.2.1]
  cases r.outcome <;> decide

end NormLabParking
