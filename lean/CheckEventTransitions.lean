import Lean
import EventTransitions

open Lean Elab Command in
run_cmd do
  let required : List Name := [
    `NormLabEvents.RecordedTransition.roundtrip,
    `NormLabEvents.RecordedTransition.added_iff,
    `NormLabEvents.RecordedTransition.removed_iff,
    `NormLabEvents.RecordedTransition.reinterpret_event,
    `NormLabEvents.RecordedTransition.reinterpret_states,
    `NormLabEvents.RecordedTransition.reinterpret_consequence,
    `NormLabEvents.RecordedTransition.different_event_is_not_reinterpretation,
    `NormLabEvents.Witness.hurricane_changes_state,
    `NormLabEvents.Witness.agent_changes_state,
    `NormLabEvents.Witness.car_changes_state,
    `NormLabEvents.Witness.alternative_roles_same_observations,
    `NormLabEvents.Witness.predecessor_is_a_separate_event]
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
