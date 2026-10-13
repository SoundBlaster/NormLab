# Offline Stage 1 seals, references and score views

Additive slice of [#77](https://github.com/SoundBlaster/NormLab/issues/77), after
the [transport adapter](OFFLINE_STAGE1_ADAPTER_V1.md). Adapter revision:
`stage1-2`. Native planners, executors, scorers, source fixtures and their frozen
pins are unchanged. This path performs no inference, resume or provider setup.

## Import

```bash
python3 -B -S evaluation/offline_adapters.py stage1 saved-capture-directory \
  --manifest fixtures/parking-pilot/stage1-coreinfra-v1/experiment.json \
  --seal saved-prediction-seal.json \
  --native-score saved-native-score.json \
  --output .artifacts/stage1-scored-bundle
python3 -B -S evaluation/offline_adapters.py verify .artifacts/stage1-scored-bundle
python3 -B -S evaluation/offline_compare.py \
  .artifacts/stage1-scored-bundle .artifacts/stage1-scored-bundle
```

All three scoring options are required together. With none, the original
transport-only import remains available. No implicit adjacent-file discovery
or seal/score creation occurs. Unsupported schemas or mismatches fail with the
fixed CLI diagnostic and exit 1 before creating the export directory.

Import requires the original pinned provenance files in the repository layout:
provider manifest → comparison parent → dataset manifest → reviewer-only labels,
plus the bound sources. External seal/score paths are explicitly selected by
the caller. Referenced provenance paths cannot escape their repository/dataset
root. The portable verifier needs only the resulting bundle and trusted reader.

## Seal and reference contracts

Supported native pairs:

| Capture     | Prediction seal                           | Score view                         |
| ----------- | ----------------------------------------- | ---------------------------------- |
| provider v1 | `normlab.stage1-prediction-seal/v1`       | `normlab.stage1-provider-score/v1` |
| retry v2    | `normlab.stage1-retry-prediction-seal/v2` | `normlab.stage1-retry-score/v2`    |

Capture replay and seal binding are validated before reviewer-only labels are
opened during import. Retry binding includes the exported split plan, outer
capture, available child plans/captures/turns and native scorer code pins.
Provider binding includes the expanded plan, capture and raw turn references.
Seals are unsigned consistency evidence; their timestamps do not establish who
created them or that labels were unseen during historical inference.

Reference import accepts only `normlab.stage1-review/v2`, with status
`candidate-not-independent` and policy `selected-claim-support`. It verifies the
manifest/dataset/labels hash chain, dataset ID, unique case/record keys, required
job coverage, source text/digests and families, and known expectations. Extra
reference rows outside the selected pilot are preserved in the original labels;
only planned jobs receive projected expectations. No human gold is inferred.

The derived `normlab.offline-stage1-reference/v1` artifact contains status,
revision, per-job `expected`, original `labelsDigest`, and references to all five
provenance inputs. The envelope reference uses its own content-derived ID.
`source.inputs` archives the seven explicitly named original inputs: manifest,
parent, dataset, sources, labels, seal and score. Their bytes are preserved.

## Deterministic score verification

The reader regenerates every field of the supplied native score: bindings,
per-job rows, arms, confusion matrices, paired denominators, first/final values,
recoveries and known/unknown usage. It requires canonical equality with the
original score; a plausible summary or matching report hash is insufficient.

The additive `offline_stage1_scoring.py` keeps the frozen native scoring formulas
separate from reference loading, reusing pure retry metrics/paired/attempt helpers.
Parity checks compare with the unchanged native scorers; native code is neither
patched nor loaded from bundle artifacts. Scorer and adapter dependencies are
bound to the trusted reader revision.

The projected `normlab.offline-stage1-report/v2` retains the transport summary,
references the original native score/seal, and includes `expected` plus nullable
`selectedReferencePass` for first and final outcomes. An unexecuted/failed/unknown
outcome remains null for paired quality evaluation, rather than becoming a
completed wrong answer. Native per-planned metrics preserve their original
denominators; unknown usage is not converted to zero consumption.

Adding a scoring view to the same saved capture does not change run identity,
capture digest, task/turn IDs or transport counts. Reference/report/scorer changes
produce a distinct score ID. The native seal is retained separately from the
envelope's derived prediction binding. This is not permission to replace pinned
labels or reinterpret a frozen native experiment without versioning it.

## Comparison and limitations

Comparison uses the **final** selected-reference result. Native first/final
metrics remain inspectable in the report, but no new comparator phase switch is
introduced. Both paired tasks must be completed and scored. Missing/failed tasks
stay in rows and planned denominators; zero eligible pairs means not evaluated.

Reference compatibility checks status, revision, expectation, label digest and
dataset/source/label provenance. Provider experiment manifests are retained for
lineage, but do not block a declared `--vary provider` change when label provenance
is identical. Undeclared provider changes remain incompatible. Transport-only
and scored views have different score scopes and cannot be treated as equivalent.

Candidate agreement is not case-level critical-error-free accuracy or a population
estimate. `semanticQualityEvidence` remains false, `criticalErrorFreeRate` null,
and no confidence interval/statistical significance is invented. Historical
captures and repeats do not establish independent executions or causal improvement.

## Portable reader

Copy the 22 modules in `offline_stage1_source.READER_FILES` into `evaluation/`
and its `READER_ASSETS` into the matching `server/` directory. Add
`offline_compare.py` for comparison. The reader verifies archived inputs without
repository fixtures, SDKs or network access. Use the exact trusted reader
revision that produced the bundle; do not execute archived code. Bounds remain
2 MiB per artifact, 64 MiB total, 4096 artifacts and 1024 tasks.

[Executed checks](OFFLINE_STAGE1_REFERENCE_2026-10-13.md).
Next slice: idempotent MLflow projection of verified bundles and score views.
