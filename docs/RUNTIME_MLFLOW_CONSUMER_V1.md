# Runtime archive consumer v1

The additive `normlab.runtime-mlflow-projection/v1` consumer accepts verified
[runtime archives](RUNTIME_ARCHIVE_V1.md). It does not reinterpret them as legacy
`offline-bundle/v1` score bundles. Existing offline import contracts are preserved.

## Identity and lineage

The SDK-free `runtime_mlflow_projection.project` maps the existing registry-plan
nodes into records with a separate `runtime-mlflow` identity namespace:

1. `runtime-execution`: immutable plan, intent and mock-script binding. Its bytes
   and key remain identical across capture revisions of the same execution.
2. `runtime-capture`: one child per exact captured source revision.
3. `runtime-projection`: one child of that capture, with the full archive index,
   task/attempt counts and an archive navigation path.
4. `runtime-prediction-seal`: an additional capture child only when the complete
   projection already contains a seal. The consumer cannot create a seal.

`parentKey` describes the import lineage; `binding` retains the original
SDK-free registry-plan identity and digest. Record digests bind their complete
canonical payload. Legacy import keys cannot collide with runtime import keys.

## Evidence boundary

Only known numeric task/attempt counts become projection metrics. Reference,
score, actual cost and critical-error-free rate remain null. Evidence stays
`mock`, unsigned and unauthenticated; readiness, semantic quality and release
approval remain false. Import is not inference or human adjudication.

`snapshot` reads and verifies the input, materializes only its verified bytes in
a temporary directory, and verifies that private copy again. Consumers upload
that copy, not the caller's mutable source directory. The archive marker and
empty lock are included, so a saved copy can be replayed independently after
the original source is removed. All existing archive byte and inventory bounds
apply. Snapshot creation uses local temporary storage; projection itself uses no
MLflow SDK, network or registry writes.

## Delivery slices

- SDK-free projection and private snapshot contract.
- Additive local MLflow importer, preserving legacy imports.
- Pinned local MLflow integration checks for repeated import, capture revisions,
  interrupted writes, drift rejection and portable artifact replay.

Canonical task: [Issue 77](https://github.com/SoundBlaster/NormLab/issues/77).
These slices do not complete the full evaluation harness acceptance.
