import Relations

-- R2a: finite sets of base signed facts. Derived closure and source identities
-- are deliberately separate. No action semantics or parking adapter is defined.
namespace NormLabStateRelations

open NormLabRelations

section Equality

variable {sig : Signature} [∀ sort, DecidableEq (sig.Entity sort)]

-- The argument sorts are fixed by the signature, so no equality decision on
-- SortId is needed. Compare values only after their dependent types coincide.
instance argsDecidableEq : {sorts : List sig.SortId} → DecidableEq (Args sig sorts)
  | [], .nil, .nil => isTrue rfl
  | _ :: _, .cons x xs, .cons y ys =>
      match decEq x y with
      | isFalse different => isFalse (fun same => different (by cases same; rfl))
      | isTrue same => by
          subst y
          match argsDecidableEq xs ys with
          | isFalse different => exact isFalse (fun same => different (by cases same; rfl))
          | isTrue same => cases same; exact isTrue rfl

instance atomDecidableEq [DecidableEq sig.Predicate] : DecidableEq (Atom sig)
  | ⟨p, xs⟩, ⟨q, ys⟩ =>
      match decEq p q with
      | isFalse different => isFalse (fun same => different (congrArg Atom.predicate same))
      | isTrue same => by
          subst q
          match decEq xs ys with
          | isFalse different => exact isFalse (fun same => different (by cases same; rfl))
          | isTrue same => cases same; exact isTrue rfl

instance literalDecidableEq [DecidableEq sig.Predicate] : DecidableEq (Literal sig)
  | ⟨p, a⟩, ⟨q, b⟩ =>
      match decEq p q, decEq a b with
      | isTrue hp, isTrue ha => isTrue (by cases hp; cases ha; rfl)
      | isFalse different, _ => isFalse (fun same => different (congrArg Literal.polarity same))
      | _, isFalse different => isFalse (fun same => different (congrArg Literal.atom same))

end Equality

-- Lists provide finite construction; quotienting by membership removes order
-- and multiplicity from semantic equality. Operations below remain computable.
def membershipSetoid (α : Type) : Setoid (List α) where
  r xs ys := ∀ x, x ∈ xs ↔ x ∈ ys
  iseqv := ⟨fun _ _ => Iff.rfl,
    fun h x => (h x).symm,
    fun h₁ h₂ x => (h₁ x).trans (h₂ x)⟩

abbrev FiniteState (α : Type) := Quotient (membershipSetoid α)
abbrev StateRelations (sig : Signature) := FiniteState (Literal sig)

namespace FiniteState

variable {α : Type} [DecidableEq α]

def ofList (xs : List α) : FiniteState α := Quotient.mk _ xs
def empty : FiniteState α := ofList []

def contains (state : FiniteState α) (x : α) : Bool :=
  Quotient.lift (fun xs => decide (x ∈ xs)) (by
    intro xs ys same
    apply decide_eq_decide.mpr
    exact same x) state

instance : Membership α (FiniteState α) := ⟨fun state x => contains state x = true⟩
instance (x : α) (state : FiniteState α) : Decidable (x ∈ state) :=
  inferInstanceAs (Decidable (contains state x = true))

@[simp] theorem mem_ofList (x : α) (xs : List α) : x ∈ ofList xs ↔ x ∈ xs := by
  change decide (x ∈ xs) = true ↔ x ∈ xs
  exact decide_eq_true_iff

@[simp] theorem not_mem_empty (x : α) : x ∉ (empty : FiniteState α) := by
  simp [empty]

theorem ext {s t : FiniteState α} (same : ∀ x, x ∈ s ↔ x ∈ t) : s = t := by
  induction s using Quotient.ind with
  | _ xs =>
    induction t using Quotient.ind with
    | _ ys =>
      apply Quotient.sound
      intro x
      exact (mem_ofList x xs).symm.trans ((same x).trans (mem_ofList x ys))

theorem ofList_eq_iff (xs ys : List α) :
    ofList xs = ofList ys ↔ ∀ x, x ∈ xs ↔ x ∈ ys := by
  constructor
  · intro same x
    simpa only [mem_ofList] using (show x ∈ ofList xs ↔ x ∈ ofList ys from same ▸ Iff.rfl)
  · intro same
    exact ext (fun x => (mem_ofList x xs).trans ((same x).trans (mem_ofList x ys).symm))

def filter (p : α → Bool) (state : FiniteState α) : FiniteState α :=
  Quotient.lift (fun xs => ofList (xs.filter p)) (by
    intro xs ys same
    apply Quotient.sound
    intro x
    simp only [List.mem_filter]
    exact and_congr_left (fun _ => same x)) state

@[simp] theorem mem_filter (p : α → Bool) (state : FiniteState α) (x : α) :
    x ∈ filter p state ↔ x ∈ state ∧ p x = true := by
  induction state using Quotient.ind with
  | _ xs =>
    change x ∈ ofList (xs.filter p) ↔ x ∈ ofList xs ∧ p x = true
    simp

def union (s t : FiniteState α) : FiniteState α :=
  Quotient.lift₂ (fun xs ys => ofList (xs ++ ys)) (by
    intro xs ys xs' ys' hx hy
    apply Quotient.sound
    intro x
    simp only [List.mem_append]
    exact or_congr (hx x) (hy x)) s t

@[simp] theorem mem_union (s t : FiniteState α) (x : α) :
    x ∈ union s t ↔ x ∈ s ∨ x ∈ t := by
  induction s, t using Quotient.ind₂ with
  | _ xs ys =>
    change x ∈ ofList (xs ++ ys) ↔ x ∈ ofList xs ∨ x ∈ ofList ys
    simp

def difference (s t : FiniteState α) : FiniteState α :=
  filter (fun x => !(contains t x)) s

@[simp] theorem mem_difference (s t : FiniteState α) (x : α) :
    x ∈ difference s t ↔ x ∈ s ∧ x ∉ t := by
  rw [difference, mem_filter]
  simp [Membership.mem]

end FiniteState

structure Delta (α : Type) where
  added : FiniteState α
  removed : FiniteState α

namespace Delta

variable {α : Type} [DecidableEq α]

def between (before after : FiniteState α) : Delta α :=
  ⟨after.difference before, before.difference after⟩

-- Removal wins only over the old state; explicit additions are then included.
def apply (before : FiniteState α) (delta : Delta α) : FiniteState α :=
  (before.difference delta.removed).union delta.added

theorem mem_added (before after : FiniteState α) (x : α) :
    x ∈ (between before after).added ↔ x ∈ after ∧ x ∉ before :=
  FiniteState.mem_difference _ _ _

theorem mem_removed (before after : FiniteState α) (x : α) :
    x ∈ (between before after).removed ↔ x ∈ before ∧ x ∉ after :=
  FiniteState.mem_difference _ _ _

theorem mem_apply (before : FiniteState α) (delta : Delta α) (x : α) :
    x ∈ apply before delta ↔ (x ∈ before ∧ x ∉ delta.removed) ∨ x ∈ delta.added := by
  simp [apply]

theorem roundtrip (before after : FiniteState α) :
    apply before (between before after) = after := by
  apply FiniteState.ext
  intro x
  simp only [mem_apply, mem_added, mem_removed]
  by_cases hb : x ∈ before <;> by_cases ha : x ∈ after <;> simp [hb, ha]

theorem self_diff (state : FiniteState α) :
    between state state = ⟨FiniteState.empty, FiniteState.empty⟩ := by
  have h : state.difference state = FiniteState.empty := by
    apply FiniteState.ext
    intro x
    simp
  simp [between, h]

theorem disjoint (before after : FiniteState α) (x : α) :
    ¬ (x ∈ (between before after).added ∧ x ∈ (between before after).removed) := by
  intro ⟨added, removed⟩
  exact ((mem_added before after x).mp added).2 ((mem_removed before after x).mp removed).1

theorem untouched (before : FiniteState α) (delta : Delta α) (x : α)
    (notAdded : x ∉ delta.added) (notRemoved : x ∉ delta.removed) :
    x ∈ apply before delta ↔ x ∈ before := by
  simp [mem_apply, notAdded, notRemoved]

-- A fact present in both states must not appear as an edit. This excludes the
-- delete-all/add-all implementation even though that implementation roundtrips.
theorem unchanged_not_edited (before after : FiniteState α) (x : α)
    (hb : x ∈ before) (ha : x ∈ after) :
    x ∉ (between before after).added ∧ x ∉ (between before after).removed := by
  simp [mem_added, mem_removed, hb, ha]

end Delta

-- A pure deletion cannot create any literal of either polarity. This statement
-- concerns base membership, not derivability under arbitrary rules.
theorem deletion_does_not_invent {sig : Signature}
    [∀ sort, DecidableEq (sig.Entity sort)] [DecidableEq sig.Predicate]
    (before removed : StateRelations sig) (atom : Atom sig)
    (absent : atom.negative ∉ before) :
    atom.negative ∉ Delta.apply before ⟨FiniteState.empty, removed⟩ := by
  simp [Delta.mem_apply, absent]

namespace Witness

-- Reuse R1's typed people, authority and episodes. Only this finite example
-- signature supplies the extra executable equality constraints.
private instance : DecidableEq NormLabRelations.Example.signature.Predicate
  | .duty, .duty | .claim, .claim => isTrue rfl
  | .duty, .claim | .claim, .duty => isFalse (by intro same; cases same)

private instance : ∀ sort, DecidableEq (NormLabRelations.Example.signature.Entity sort) := by
  intro sort
  cases sort with
  | person => exact inferInstanceAs (DecidableEq NormLabRelations.Example.Person)
  | authority => exact inferInstanceAs (DecidableEq NormLabRelations.Example.Authority)
  | episode => exact inferInstanceAs (DecidableEq NormLabRelations.Example.Episode)

open NormLabRelations.Example (signature duty claim)

def positiveDuty : Literal signature := (duty .alice .office .first).positive
def negativeDuty : Literal signature := (duty .alice .office .first).negative
def positiveClaim : Literal signature := (claim .office .alice .first).positive
def before : StateRelations signature := FiniteState.ofList [positiveDuty, negativeDuty]
def after : StateRelations signature := FiniteState.ofList [negativeDuty, positiveClaim]

theorem order_and_duplicates :
    FiniteState.ofList [positiveDuty, negativeDuty, positiveDuty] =
      FiniteState.ofList [negativeDuty, positiveDuty] := by
  apply FiniteState.ext
  intro x
  simp only [FiniteState.mem_ofList, List.mem_cons, List.not_mem_nil, or_false]
  constructor
  · rintro (h | h | h)
    · exact Or.inr h
    · exact Or.inl h
    · exact Or.inr h
  · rintro (h | h)
    · exact Or.inr (Or.inl h)
    · exact Or.inl h

theorem nonempty_change :
    positiveClaim ∈ (Delta.between before after).added ∧
    positiveDuty ∈ (Delta.between before after).removed ∧
    negativeDuty ∈ Delta.apply before (Delta.between before after) := by decide

theorem opposed_evidence_is_preserved :
    positiveDuty ∈ before ∧ negativeDuty ∈ before ∧
    Delta.apply before (Delta.between before before) = before :=
  ⟨by decide, by decide, Delta.roundtrip before before⟩

theorem removed_positive_does_not_add_negative :
    negativeDuty ∉ Delta.apply (FiniteState.ofList [positiveDuty])
      ⟨FiniteState.empty, FiniteState.ofList [positiveDuty]⟩ := by decide

def overbroad : Delta (Literal signature) := ⟨after, before⟩

theorem overbroad_roundtrips : Delta.apply before overbroad = after := by
  apply FiniteState.ext
  intro x
  simp [Delta.mem_apply, overbroad]

theorem overbroad_is_not_exact :
    negativeDuty ∈ overbroad.added ∧ negativeDuty ∈ before ∧
    negativeDuty ∉ (Delta.between before after).added ∧
    overbroad ≠ Delta.between before after := by
  refine ⟨by decide, by decide, by decide, ?_⟩
  intro same
  have member : negativeDuty ∈ overbroad.added := by decide
  rw [same] at member
  exact (by decide : negativeDuty ∉ (Delta.between before after).added) member

end Witness

end NormLabStateRelations
