# Pipeline quality corpus inventory v1

Development inventory for the [agreed pipeline quality plan](../../../docs/PIPELINE_QUALITY_PLAN.md).
This is metadata for maintainers/reviewers, not model input or a new labelled dataset.

`corpus-inventory.json` references the existing immutable texts and pins their
manifest/source hashes. Namespaced dataset IDs distinguish Stage 1 C001 from
editorial C01. All 71 inputs remain development-only. Exact hashes differ, but
semantic independence and cross-dataset family/source grouping still require
manual review. No holdout cases or gold case-pass scores are established here.

```sh
python3 -B -S evaluation/audit_pipeline_corpus.py --check
```

CI checks that the inventory matches the current source bytes. It does not
validate labels, source truth, semantic independence or extraction completeness.
The script's write mode refuses to overwrite a file; regenerate to a new path
and review the diff before replacing this inventory. No SDK/key/network access.
