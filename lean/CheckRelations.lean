import Lean
import Relations

-- CI checks actual kernel declarations, not the text printed by #print axioms.
-- Compile Relations.lean to a fresh external directory and put it on LEAN_PATH.
open Lean Elab Command in
run_cmd do
  let required : List Name := [
    `NormLabRelations.soundness,
    `NormLabRelations.canonicalModel_models,
    `NormLabRelations.canonicalModel_least,
    `NormLabRelations.completeness,
    `NormLabRelations.derivable_iff_semantic_consequence,
    `NormLabRelations.not_derivable_iff_countermodel,
    `NormLabRelations.monotonicity,
    `NormLabRelations.not_derivable_of_countermodel,
    `NormLabRelations.derivable_without_rules_iff,
    `NormLabRelations.opposed_support_without_explosion,
    `NormLabRelations.DutyClaim.imageModel_models,
    `NormLabRelations.DutyClaim.claim_derivable_iff_mem,
    `NormLabRelations.Example.supported_claim,
    `NormLabRelations.Example.countermodel_nonempty,
    `NormLabRelations.Example.countermodel_models,
    `NormLabRelations.Example.wrong_person_not_derivable,
    `NormLabRelations.Example.wrong_episode_not_derivable,
    `NormLabRelations.Example.missing_support_is_not_negative,
    `NormLabRelations.Example.conflicting_duty_without_claim]
  for name in required do
    let info ← getConstInfo name
    unless info.isTheorem do
      throwError "Required relation theorem is missing or has changed kind: {name}"
  let env ← getEnv
  let mut checked := 0
  for (name, info) in env.constants.toList do
    let userName := (privateToUserName? name).getD name
    if (`NormLabRelations).isPrefixOf userName then
      if info.isAxiom then
        throwError "Custom axiom in relation core: {name}"
      if info.isTheorem then
        let axioms ← collectAxioms name
        for axiomName in axioms do
          unless axiomName == `propext do
            throwError "Disallowed axiom {axiomName} in relation theorem {name}"
        checked := checked + 1
  logInfo m!"Relation axiom gate passed: {checked} theorem declarations; allowlist: [propext]"
