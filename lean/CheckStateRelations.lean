import Lean
import StateRelations

-- Quot.sound is needed for finite-set equality modulo order and duplicates.
-- Classical.choice and sorryAx are not allowed, including in executable defs.
open Lean Elab Command in
run_cmd do
  let required : List Name := [
    `NormLabStateRelations.FiniteState.mem_ofList,
    `NormLabStateRelations.FiniteState.not_mem_empty,
    `NormLabStateRelations.FiniteState.ext,
    `NormLabStateRelations.FiniteState.ofList_eq_iff,
    `NormLabStateRelations.FiniteState.mem_filter,
    `NormLabStateRelations.FiniteState.mem_union,
    `NormLabStateRelations.FiniteState.mem_difference,
    `NormLabStateRelations.Delta.mem_added,
    `NormLabStateRelations.Delta.mem_removed,
    `NormLabStateRelations.Delta.mem_apply,
    `NormLabStateRelations.Delta.roundtrip,
    `NormLabStateRelations.Delta.self_diff,
    `NormLabStateRelations.Delta.disjoint,
    `NormLabStateRelations.Delta.untouched,
    `NormLabStateRelations.Delta.unchanged_not_edited,
    `NormLabStateRelations.deletion_does_not_invent,
    `NormLabStateRelations.Witness.order_and_duplicates,
    `NormLabStateRelations.Witness.nonempty_change,
    `NormLabStateRelations.Witness.opposed_evidence_is_preserved,
    `NormLabStateRelations.Witness.removed_positive_does_not_add_negative,
    `NormLabStateRelations.Witness.overbroad_roundtrips,
    `NormLabStateRelations.Witness.overbroad_is_not_exact]
  for name in required do
    let info ← getConstInfo name
    unless info.isTheorem do
      throwError "Required state theorem is missing or has changed kind: {name}"
  let env ← getEnv
  let mut checked := 0
  let mut theorems := 0
  for (name, info) in env.constants.toList do
    let userName := (privateToUserName? name).getD name
    if (`NormLabStateRelations).isPrefixOf userName then
      if info.isAxiom then
        throwError "Custom axiom in state core: {name}"
      let axioms ← collectAxioms name
      for axiomName in axioms do
        unless axiomName == `propext || axiomName == `Quot.sound do
          throwError "Disallowed axiom {axiomName} in state declaration {name}"
      checked := checked + 1
      if info.isTheorem then theorems := theorems + 1
  logInfo m!"State axiom gate passed: {checked} declarations, {theorems} theorems; allowlist: [propext, Quot.sound]"
