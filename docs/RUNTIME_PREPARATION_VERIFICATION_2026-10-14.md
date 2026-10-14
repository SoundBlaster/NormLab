# Runtime preparation stack: verification and handoff

Date: 2026-10-14. Related task: [#77](https://github.com/SoundBlaster/NormLab/issues/77).
Three dependent preparation layers above the corrected 5c branch:

1. [5d.1 capture revisions](RUNTIME_CAPTURE_PREPARATION_V1.md): validated source
   inventory and in-memory snapshots; original execution/new capture identity.
2. [5d.2 export projection](RUNTIME_EXPORT_PREPARATION_V1.md): separate task
   artifacts, full denominator/attempt history and complete-only mock seals.
3. [5d.3 registry plan](RUNTIME_REGISTRY_PREPARATION_V1.md): immutable execution,
   capture, projection/seal nodes and create/reuse/conflict reconciliation.

## Local evidence

| Check                                         | Result                                                                       |
| --------------------------------------------- | ---------------------------------------------------------------------------- |
| Dedicated runtime preparation, Python 3.14.8  | 18/18 in 2.050s                                                              |
| Dedicated runtime preparation, Python 3.10.19 | 18/18 in 2.086s                                                              |
| Complete stdlib offline suite, Python 3.14.8  | 155/155 in 124.106s                                                          |
| Ruff lint/format                              | 106 Python files pass                                                        |
| Syntax, Markdown, links and staged whitespace | 14 Python AST parses, 47 relative links, Prettier and staged whitespace pass |
| GitHub CI and independent PR review           | Separate gates; fresh result recorded in ledger/PRs                          |
| Provider calls / registry writes / deployment | None                                                                         |

```bash
python -B -S -m unittest discover -s evaluation -p 'test_offline_runtime_*.py' -v
python -B -S -m unittest discover -s evaluation -p 'test_offline_*.py' -v
ruff check --select E4,E7,E9,F,I evaluation
ruff format --check evaluation
```

Runtime scenarios cover repeated exact identity/source bytes, defensive copies,
immutable byte maps, original snapshot retention after continuation, exclusion
of adjacent/orphan files, stale manifest rejection, all-task/unknown suffix
preservation, retry first/final and charges, adoption without a new reservation,
complete-only mock seals, edited/rehashed summaries and records, and a
288-task/864-question unstarted matrix with separate bounded task artifacts.
Registry scenarios cover same-node reuse, same execution/new revision children,
unmodified prior receipts, unknown usage, absent score/seal for partial captures,
key/digest/kind/parent conflicts, duplicate receipts and changed action/metric/
approval claims. CLI probes run under write/network/SDK-denial guards.

The two original #96 P2 findings were reproduced and fixed before layering:
all four requested caps must cover past reserved totals; directories stay in
publication entry accounting with zero byte size. [5c verification history](MOCK_RESUME_VERIFICATION_2026-10-14.md)
records 22/22 dedicated and 137/137 complete offline checks for that correction.

## Remaining work and acceptance

This stack prepares schemas/projections and checks their lineage; it does not
produce a durable portable runtime archive or integrate these schemas into the
existing offline-envelope/MLflow importer. CLI plans and generated seals remain
unsigned mock evidence. `verify` APIs compare with a saved runtime root; they
are not independent readers for historical archived captures. Actual archive
publication, versioned consumer compatibility, reference/score wiring and real
registry write/recovery need separate implementation and verification.

Next concrete result: durable runtime archive + portable reader, preserving
original and continued revisions, then archive/import round trips. Existing
native runners/scorers, frozen fixture/dependency pins and legacy importer
behavior remain unchanged. #77 remains open/in-progress; CI/review and broader
acceptance are outstanding. No live/provider/semantic-quality readiness is
inferred from these local checks.
