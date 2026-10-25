import Lean
import ParkingRuntime

open Lean Elab Command in
run_cmd do
  let required : List Name := [
    `NormLabParkingRuntime.accepted_scope,
    `NormLabParkingRuntime.accepted_snapshot,
    `NormLabParkingRuntime.source_identities,
    `NormLabParkingRuntime.supports_scoped]
  for name in required do
    let info ← getConstInfo name
    unless info.isTheorem do
      throwError "Required runtime-binding theorem missing: {name}"
  let env ← getEnv
  let mut checked := 0
  for (name, info) in env.constants.toList do
    let userName := (privateToUserName? name).getD name
    if (`NormLabParkingRuntime).isPrefixOf userName then
      if info.isAxiom then
        throwError "Custom axiom in runtime binding: {name}"
      for axiomName in (← collectAxioms name) do
        unless axiomName == `propext || axiomName == `Quot.sound do
          throwError "Disallowed axiom {axiomName} in runtime binding {name}"
      for expression in info.type :: (info.value? true).toList do
        for dependency in expression.getUsedConstants do
          if (`NormLabActionAttribution.Profile.proposeUnbound).isPrefixOf dependency ||
              (`NormLabActionAttribution.Profile.UnboundTransition).isPrefixOf dependency then
            throwError "Runtime binding directly references unbound API: {dependency}"
      checked := checked + 1
  logInfo m!"Runtime binding gate passed: {checked} declarations; no direct unbound API; allowlist: [propext, Quot.sound]"
