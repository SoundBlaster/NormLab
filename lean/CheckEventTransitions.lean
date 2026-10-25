import Lean
import EventTransitions

open Lean Elab Command in
run_cmd do
  let required : List Name := [
    `NormLabEvents.EventRegistry.ofList_lookup,
    `NormLabEvents.EventRegistry.ofList_lookup_iff,
    `NormLabEvents.EventRegistry.ofList?_isSome_iff,
    `NormLabEvents.EventRegistry.ofList?_duplicate_rejected,
    `NormLabEvents.RecordedEvent.roundtrip,
    `NormLabEvents.RecordedEvent.added_iff,
    `NormLabEvents.RecordedEvent.removed_iff,
    `NormLabEvents.Interpretation.same_observations,
    `NormLabEvents.Interpretation.same_consequence,
    `NormLabEvents.Interpretation.context_key,
    `NormLabEvents.RegisteredEvent.same_id_same_record,
    `NormLabEvents.RegisteredEvent.same_id_same_key,
    `NormLabEvents.RegisteredEvent.same_id_same_observations,
    `NormLabEvents.RegisteredEvent.missing_record_rejected,
    `NormLabEvents.CausalHypothesis.no_self,
    `NormLabEvents.CausalHypothesis.no_backwards_start,
    `NormLabEvents.CausalHypothesis.ordered_endpoints,
    `NormLabEvents.Witness.hurricane_changes_state,
    `NormLabEvents.Witness.agent_changes_state,
    `NormLabEvents.Witness.car_changes_state,
    `NormLabEvents.Witness.alternative_roles_same_observations,
    `NormLabEvents.Witness.overlapping_cause_accepted,
    `NormLabEvents.Witness.self_cause_rejected,
    `NormLabEvents.Witness.ghost_record_rejected,
    `NormLabEvents.Witness.changed_observations_rejected,
    `NormLabEvents.Witness.missing_event_rejected]
  for name in required do
    let info ← getConstInfo name
    unless info.isTheorem do
      throwError "Required event theorem is missing or has changed kind: {name}"
  let env ← getEnv
  let mut checked := 0
  let mut theorems := 0
  for (name, info) in env.constants.toList do
    let userName := (privateToUserName? name).getD name
    if (`NormLabEvents).isPrefixOf userName then
      if info.isAxiom then
        throwError "Custom axiom in event core: {name}"
      let axioms ← collectAxioms name
      for axiomName in axioms do
        unless axiomName == `propext || axiomName == `Quot.sound do
          throwError "Disallowed axiom {axiomName} in event declaration {name}"
      checked := checked + 1
      if info.isTheorem then theorems := theorems + 1
  logInfo m!"Event axiom gate passed: {checked} declarations, {theorems} theorems; allowlist: [propext, Quot.sound]"
