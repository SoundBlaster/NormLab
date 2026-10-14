# Capture-revision-aware registry planning: 5d.3

Date: 2026-10-14. Related task: [#77](https://github.com/SoundBlaster/NormLab/issues/77).
Depends on [5d.2 export projection](RUNTIME_EXPORT_PREPARATION_V1.md).
Implementation: [registry planner](../evaluation/runtime_registry.py).

## Commands and scope

```bash
python -B -S evaluation/runtime_capture_cli.py registry-plan /path/to/mock-execution
python -B -S evaluation/runtime_capture_cli.py registry-plan /path/to/mock-execution --receipts /path/to/known-bindings.json
```

These are SDK-free, read-only planning commands. They open no MLflow storage,
create no SQLite database and write no receipts, metrics or artifacts. A supplied
receipt list describes known bindings for comparison; it does not attest that
such registry objects exist. Invalid input yields sanitized exit 2. This schema
is distinct from an existing offline bundle and is not accepted by the current
MLflow importer.

## Identity and reconciliation

The generated `normlab.runtime-registry-plan/v1` contains parent-before-child
nodes with `{key, kind, parentKey, bindingDigest}`:

| Kind              | Key binding                         | Immutable digest / parent                                         |
| ----------------- | ----------------------------------- | ----------------------------------------------------------------- |
| `execution`       | Runtime execution ID                | Execution ID, plan, original intent and script digests; no parent |
| `capture`         | Execution + capture revision ID     | Complete capture manifest; execution parent                       |
| `projection`      | Projection ID                       | Exact export plan; capture parent                                 |
| `prediction-seal` | Seal ID, only for complete captures | Exact mock seal artifact; capture parent                          |

The stable execution parent excludes changing checkpoints, counters and scores.
New capture revisions create new children rather than overwriting a parent or
prior revision. An identical node proposes `reuse`; an absent node proposes
`create`. Same-key digest, kind or parent mismatch rejects as conflict. Duplicate
receipts reject even if identical, because ambiguous registry identity must be
investigated. Old/unrelated valid receipts are left untouched. Receipt fields,
digest/text shape, 4096-entry and 2 MiB input limits are checked.

Plan identity covers nodes, proposed actions, metrics/navigation and flags.
`verify_registry_plan(root, plan, receipts)` regenerates source-bound expectations
and rejects changed actions, counts, bindings or approval/write claims. Receipts
and export projections are never mutated by planning. This is not recovery of
actual registry writes; durable ledger/MLflow reconciliation is a later consumer.

## Metrics, navigation and gates

Only mock task/attempt denominators, reserved caps and known/unknown token usage
are projected. Partial and unknown captures get no prediction-seal or score node.
Reference/score/actual cost remain null; release-approved, execution-ready and
semantic-quality flags remain false. New inference and registry writes are zero.
Navigation retains the source inventory and capture/task/seal artifact references
for the future archive consumer, without claiming those bytes have been uploaded.

Six regression methods verify repeat reuse, changing revision/stable execution,
old revision retention, partial/unknown evidence, conflicts/duplicate receipts,
edited plans and write/network/SDK-denied CLI. Combined evidence for all three
layers is in the [stack verification report](RUNTIME_PREPARATION_VERIFICATION_2026-10-14.md).

Next after review: implement a **durable portable runtime export and its reader**,
then wire the runtime schemas into the existing envelope/MLflow consumer and
verify archive/import round trips and crash recovery. Preparation alone does not
complete the 5d gate. Host-clock/current authorization/code/provider attestation,
native normalization/transport and separately authorized live smoke remain
later gates. No provider request, credential, deployment or new dependency is
introduced by this stack.
