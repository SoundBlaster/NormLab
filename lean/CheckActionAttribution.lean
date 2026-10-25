import Lean
import ActionAttribution

open Lean Elab Command in
run_cmd do
  let required : List Name := [
    `NormLabActionAttribution.humanCandidate_context,
    `NormLabActionAttribution.contextOf_literal,
    `NormLabActionAttribution.literal_context_injective,
    `NormLabActionAttribution.certificate_uses_facts,
    `NormLabActionAttribution.certificate_uses_rule,
    `NormLabActionAttribution.clear_iff,
    `NormLabActionAttribution.check_iff,
    `NormLabActionAttribution.checked_provenance,
    `NormLabActionAttribution.checked_rule_authorized,
    `NormLabActionAttribution.checked_action_has_performance,
    `NormLabActionAttribution.checked_actor_attributed,
    `NormLabActionAttribution.unattributed_actor_rejected,
    `NormLabActionAttribution.checked_omission_has_nonperformance,
    `NormLabActionAttribution.checked_omission_conditions,
    `NormLabActionAttribution.checked_has_scoped_fact,
    `NormLabActionAttribution.checked_scope_preserved,
    `NormLabActionAttribution.unknown_nonperformance_rejected,
    `NormLabActionAttribution.opposed_nonperformance_rejected,
    `NormLabActionAttribution.unauthorized_profile_rejected,
    `NormLabActionAttribution.mem_after,
    `NormLabActionAttribution.frame,
    `NormLabActionAttribution.exact_added,
    `NormLabActionAttribution.nothing_removed,
    `NormLabActionAttribution.consequence_roundtrip,
    `NormLabActionAttribution.propose_isSome_iff,
    `NormLabActionAttribution.GroundedTransition.provenance,
    `NormLabActionAttribution.GroundedTransition.roundtrip,
    `NormLabActionAttribution.GroundedTransition.added_has_grounds,
    `NormLabActionAttribution.Witness.direct_action_accepted,
    `NormLabActionAttribution.Witness.abstract_actor_accepted,
    `NormLabActionAttribution.Witness.abstract_actor_is_not_human,
    `NormLabActionAttribution.Witness.omission_accepted,
    `NormLabActionAttribution.Witness.self_action_accepted,
    `NormLabActionAttribution.Witness.attribution_cannot_be_skipped,
    `NormLabActionAttribution.Witness.scope_substitution_rejected,
    `NormLabActionAttribution.Witness.event_interpretation_substitution_rejected,
    `NormLabActionAttribution.Witness.unknown_is_not_omission,
    `NormLabActionAttribution.Witness.conflict_is_not_omission,
    `NormLabActionAttribution.Witness.missing_conditions_rejected,
    `NormLabActionAttribution.Witness.direct_candidate_cannot_bypass,
    `NormLabActionAttribution.Witness.unrelated_rule_cannot_bypass,
    `NormLabActionAttribution.Witness.nonempty_exact_effect,
    `NormLabActionAttribution.Witness.unrelated_conflict_retained,
    `NormLabActionAttribution.Witness.output_is_not_derived_closure,
    `NormLabActionAttribution.Witness.general_event_without_human_profile]
  for name in required do
    let info ← getConstInfo name
    unless info.isTheorem do
      throwError "Required attribution theorem is missing or has changed kind: {name}"
  let env ← getEnv
  let mut checked := 0
  let mut theorems := 0
  for (name, info) in env.constants.toList do
    let userName := (privateToUserName? name).getD name
    if (`NormLabActionAttribution).isPrefixOf userName then
      if info.isAxiom then
        throwError "Custom axiom in action attribution: {name}"
      let axioms ← collectAxioms name
      for axiomName in axioms do
        unless axiomName == `propext || axiomName == `Quot.sound do
          throwError "Disallowed axiom {axiomName} in attribution declaration {name}"
      checked := checked + 1
      if info.isTheorem then theorems := theorems + 1
  logInfo m!"Attribution axiom gate passed: {checked} declarations, {theorems} theorems; allowlist: [propext, Quot.sound]"
