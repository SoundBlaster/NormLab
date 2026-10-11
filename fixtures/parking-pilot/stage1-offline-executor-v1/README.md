# Offline executor rehearsal v1

`summaries.json` contains deterministic control-flow summaries from synthetic wire
fixtures for the three frozen comparison profiles. Regenerate each through
`evaluation/stage1_executor.py --mock-output NEW_DIRECTORY`, then compare its stdout
or replay output with the corresponding entry.

There are **zero provider calls**. Labels cycle by job index; they do not come from
a model or the reviewer labels. Model suffixes and request IDs identify fixtures.
Full captures are local, ignored `.artifacts/` data and are reproducible from the
frozen protocol plus this executor version.

See [contract, commands and limitations](../../../docs/STAGE1_OFFLINE_EXECUTOR.md).
