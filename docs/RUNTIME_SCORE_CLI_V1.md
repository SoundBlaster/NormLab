# Offline runtime score export and verification

```bash
python evaluation/runtime_score_cli.py score ARCHIVE labels.json --output score.json
python evaluation/runtime_score_cli.py score ARCHIVE reviewed-labels.json \
  --review review.json --output reviewed-score.json
python evaluation/runtime_score_cli.py verify ARCHIVE score.json
```

The archive is fully verified **before labels are opened**. Label sources and
review artifacts follow the [reference contract](RUNTIME_REFERENCE_V1.md).
Candidate references do not take `--review`. A declared human reference requires
at least one source-bound review. The command never invokes a provider SDK,
launches inference or imports into MLflow.

`score` creates a separate [score view](RUNTIME_SCORE_VIEW_V1.md); no archive
files change. Output must be a fresh filename in an existing directory outside
the archive tree; resolved archive aliases are also rejected. The CLI
flushes a temporary file before linking it to the output name without overwrite.
A failure before publication creates no output marker. If an error occurs after
publication, the complete file may remain: run `verify` rather than assuming
an error means no file exists. Local fsync is not physical power-loss attestation.

`verify` reconstructs embedded reference bytes and recomputes scores using the
matching installed trusted scorer. Original label/review files and runtime source
are unnecessary; the portable archive and installed trusted modules are required.
Scorer code pin drift rejects instead of silently changing historical metrics.
Changing source labels creates a new reference ID and a distinct score view.

Successful stdout contains IDs, summary and evidence flags. Input/storage errors
print only an error type, with no labels, raw responses or paths. Each view is
bounded by 2 MiB; over-limit inputs/views fail without truncation. There is no
automatic fallback, label generation, score upload, quality claim or release
approval. MLflow score-child integration remains a later independent slice.

Canonical task: [Issue 77](https://github.com/SoundBlaster/NormLab/issues/77).
