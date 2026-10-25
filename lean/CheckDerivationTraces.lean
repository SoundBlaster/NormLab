import Lean
import DerivationTraces

open Lean Elab Command in
run_cmd do
  let required : List Name := [
    `NormLabDerivationTraces.Tree.inductionTree,
    `NormLabDerivationTraces.Tree.soundness,
    `NormLabDerivationTraces.Tree.certificate_exists,
    `NormLabDerivationTraces.Tree.derivable_iff_certificate,
    `NormLabDerivationTraces.Tree.valid_uses_facts,
    `NormLabDerivationTraces.Tree.valid_uses_rules,
    `NormLabDerivationTraces.Tree.preserve_support,
    `NormLabDerivationTraces.Tree.derivable_of_preserved_support,
    `NormLabDerivationTraces.Tree.valid_congr_membership,
    `NormLabDerivationTraces.Tree.check_iff_valid,
    `NormLabDerivationTraces.Tree.reject_missing_fact,
    `NormLabDerivationTraces.Tree.reject_missing_rule,
    `NormLabDerivationTraces.Tree.verify_iff,
    `NormLabDerivationTraces.Tree.verify_sound,
    `NormLabDerivationTraces.Tree.derivable_iff_verified,
    `NormLabDerivationTraces.mem_remove,
    `NormLabDerivationTraces.ofList_remove,
    `NormLabDerivationTraces.Tree.preserve_under_deletion,
    `NormLabDerivationTraces.Tree.verify_after_deletion,
    `NormLabDerivationTraces.Witness.independent_certificates,
    `NormLabDerivationTraces.Witness.support_is_local,
    `NormLabDerivationTraces.Witness.malformed_children_rejected,
    `NormLabDerivationTraces.Witness.wrong_target_rejected,
    `NormLabDerivationTraces.Witness.alternate_after_fact_deletion,
    `NormLabDerivationTraces.Witness.alternate_after_rule_deletion,
    `NormLabDerivationTraces.Witness.unused_deletions_preserve_selected_tree,
    `NormLabDerivationTraces.Witness.no_result_without_both_bases]
  for name in required do
    let info ← getConstInfo name
    unless info.isTheorem do
      throwError "Required trace theorem is missing or has changed kind: {name}"
  let env ← getEnv
  let mut checked := 0
  let mut theorems := 0
  for (name, info) in env.constants.toList do
    let userName := (privateToUserName? name).getD name
    if (`NormLabDerivationTraces).isPrefixOf userName then
      if info.isAxiom then
        throwError "Custom axiom in derivation trace core: {name}"
      let axioms ← collectAxioms name
      for axiomName in axioms do
        unless axiomName == `propext || axiomName == `Quot.sound do
          throwError "Disallowed axiom {axiomName} in trace declaration {name}"
      checked := checked + 1
      if info.isTheorem then theorems := theorems + 1
  logInfo m!"Trace axiom gate passed: {checked} declarations, {theorems} theorems; allowlist: [propext, Quot.sound]"
