import Lean
import ActionAttribution

open Lean Elab Command in
run_cmd do
  let required : List Name := [
    `NormLabActionAttribution.HumanContext.scope_key,
    `NormLabActionAttribution.HumanContext.registration,
    `NormLabActionAttribution.propose_isSome_iff,
    `NormLabActionAttribution.GroundedTransition.registration,
    `NormLabActionAttribution.GroundedTransition.provenance,
    `NormLabActionAttribution.GroundedTransition.roundtrip,
    `NormLabActionAttribution.GroundedTransition.added_has_event,
    `NormLabActionAttribution.GroundedTransition.no_breach_for_other_event,
    `NormLabActionAttribution.CarWitness.omission_accepted,
    `NormLabActionAttribution.CarWitness.bound_omission_proposal,
    `NormLabActionAttribution.CarWitness.breach_not_transferred_to_motion,
    `NormLabActionAttribution.CarWitness.omission_adds_its_own_breach,
    `NormLabActionAttribution.CarWitness.integrated_chain,
    `NormLabActionAttribution.CarWitness.raw_ghost_is_not_bound,
    `NormLabActionAttribution.CarWitness.absent_context_rejected,
    `NormLabActionAttribution.CarWitness.general_event_without_human_profile,
    `NormLabActionAttribution.Profile.scopeWithHuman_context,
    `NormLabActionAttribution.Profile.contextOf_literal,
    `NormLabActionAttribution.Profile.literal_context_injective,
    `NormLabActionAttribution.Profile.certificate_uses_facts,
    `NormLabActionAttribution.Profile.certificate_uses_rule,
    `NormLabActionAttribution.Profile.clear_iff,
    `NormLabActionAttribution.Profile.check_iff,
    `NormLabActionAttribution.Profile.checked_provenance,
    `NormLabActionAttribution.Profile.checked_rule_authorized,
    `NormLabActionAttribution.Profile.checked_action_has_performance,
    `NormLabActionAttribution.Profile.checked_actor_attributed,
    `NormLabActionAttribution.Profile.unattributed_actor_rejected,
    `NormLabActionAttribution.Profile.checked_omission_has_nonperformance,
    `NormLabActionAttribution.Profile.checked_omission_conditions,
    `NormLabActionAttribution.Profile.checked_has_scoped_fact,
    `NormLabActionAttribution.Profile.checked_scope_preserved,
    `NormLabActionAttribution.Profile.unknown_nonperformance_rejected,
    `NormLabActionAttribution.Profile.opposed_nonperformance_rejected,
    `NormLabActionAttribution.Profile.unauthorized_profile_rejected,
    `NormLabActionAttribution.Profile.mem_after,
    `NormLabActionAttribution.Profile.frame,
    `NormLabActionAttribution.Profile.exact_added,
    `NormLabActionAttribution.Profile.nothing_removed,
    `NormLabActionAttribution.Profile.consequence_roundtrip,
    `NormLabActionAttribution.Profile.propose_isSome_iff,
    `NormLabActionAttribution.Profile.GroundedTransition.provenance,
    `NormLabActionAttribution.Profile.GroundedTransition.roundtrip,
    `NormLabActionAttribution.Profile.GroundedTransition.added_has_grounds,
    `NormLabActionAttribution.Profile.Witness.direct_action_accepted,
    `NormLabActionAttribution.Profile.Witness.abstract_actor_accepted,
    `NormLabActionAttribution.Profile.Witness.abstract_actor_is_not_human,
    `NormLabActionAttribution.Profile.Witness.omission_accepted,
    `NormLabActionAttribution.Profile.Witness.self_action_accepted,
    `NormLabActionAttribution.Profile.Witness.attribution_cannot_be_skipped,
    `NormLabActionAttribution.Profile.Witness.scope_substitution_rejected,
    `NormLabActionAttribution.Profile.Witness.event_interpretation_substitution_rejected,
    `NormLabActionAttribution.Profile.Witness.unknown_is_not_omission,
    `NormLabActionAttribution.Profile.Witness.conflict_is_not_omission,
    `NormLabActionAttribution.Profile.Witness.missing_conditions_rejected,
    `NormLabActionAttribution.Profile.Witness.direct_candidate_cannot_bypass,
    `NormLabActionAttribution.Profile.Witness.unrelated_rule_cannot_bypass,
    `NormLabActionAttribution.Profile.Witness.nonempty_exact_effect,
    `NormLabActionAttribution.Profile.Witness.unrelated_conflict_retained,
    `NormLabActionAttribution.Profile.Witness.output_is_not_derived_closure,
    `NormLabActionAttribution.Profile.Witness.general_event_without_human_profile]
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
