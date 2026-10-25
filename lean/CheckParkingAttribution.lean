import Lean
import ParkingAttribution

open Lean Elab Command in
run_cmd do
  let required : List Name := [
    `NormLabParkingAttribution.propose_isSome_iff,
    `NormLabParkingAttribution.accepted_record,
    `NormLabParkingAttribution.accepted_scope,
    `NormLabParkingAttribution.accepted_context,
    `NormLabParkingAttribution.Witness.omission_accepted,
    `NormLabParkingAttribution.Witness.driver_not_owner,
    `NormLabParkingAttribution.Witness.unknown_rejected,
    `NormLabParkingAttribution.Witness.duplicate_ids_rejected]
  for name in required do
    let info ← getConstInfo name
    unless info.isTheorem do
      throwError "Required parking-boundary theorem is missing: {name}"
  let env ← getEnv
  let mut checked := 0
  let mut theorems := 0
  for (name, info) in env.constants.toList do
    let userName := (privateToUserName? name).getD name
    if (`NormLabParkingAttribution).isPrefixOf userName then
      if info.isAxiom then
        throwError "Custom axiom in parking boundary: {name}"
      let axioms ← collectAxioms name
      for axiomName in axioms do
        unless axiomName == `propext || axiomName == `Quot.sound do
          throwError "Disallowed axiom {axiomName} in parking declaration {name}"
      -- Inspect direct references in the parking module's types and bodies.
      -- Bound API internals may delegate to Profile; this is not a transitive ban.
      let expressions := info.type :: (info.value? true).toList
      for expression in expressions do
        for dependency in expression.getUsedConstants do
          if (`NormLabActionAttribution.Profile.proposeUnbound).isPrefixOf dependency ||
              (`NormLabActionAttribution.Profile.UnboundTransition).isPrefixOf dependency ||
              (`NormLabActionAttribution.Profile.propose).isPrefixOf dependency ||
              (`NormLabActionAttribution.Profile.GroundedTransition).isPrefixOf dependency then
            throwError "Parking boundary references unbound API {dependency} in {name}"
      checked := checked + 1
      if info.isTheorem then theorems := theorems + 1
  logInfo m!"Parking boundary gate passed: {checked} declarations, {theorems} theorems; no direct unbound API; allowlist: [propext, Quot.sound]"
