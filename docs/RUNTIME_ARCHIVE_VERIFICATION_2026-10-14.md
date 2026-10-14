# Runtime archive stack: local verification

Date: 2026-10-14. Task: [#77](https://github.com/SoundBlaster/NormLab/issues/77).
Base: `b7df11bba0779b136c08ee1c4bd47d50ca44532c` (stack #100 merge).
Contract: [runtime archive v1](RUNTIME_ARCHIVE_V1.md).

## Results

| Check                                                 | Result                                                                      |
| ----------------------------------------------------- | --------------------------------------------------------------------------- |
| Dedicated archive suite, Python 3.14.8 / macOS        | 21/21 in 3.876s                                                             |
| Dedicated archive suite, Python 3.10.19 / macOS       | 21/21 in 3.997s                                                             |
| Complete stdlib SDK-free offline suite, Python 3.14.8 | 176/176 in 141.833s                                                         |
| Ruff lint/format                                      | All 113 Python files pass                                                   |
| AST, Markdown, links and staged whitespace            | Seven Python parses, 35 relative links, Prettier and staged whitespace pass |
| GitHub CI and independent PR review                   | Separate gates, recorded in PR/ledger                                       |
| Provider calls / registry writes / deployment         | None                                                                        |

```bash
python -B -S -m unittest discover -s evaluation -p 'test_offline_runtime_archive_*.py' -v
python -B -S -m unittest discover -s evaluation -p 'test_offline_*.py' -v
ruff check --select E4,E7,E9,F,I evaluation
ruff format --check evaluation
```

## Executed scenarios

- Four format methods establish deterministic index/source/projection names,
  immutable copies and retention of original v1 bytes in a continued v2 archive.
  Invalid shape/type/path/pin-set/ref/totals mutations reject after rehashing.
  File/byte limits account for metadata, directories, final marker and lock.
- Four writer methods verify exact content, commit-marker/barrier ordering,
  reader contention, no overwrite/second publication and real fsync OSError.
  Ten hook interruption points cover directory/lock/content/marker publication;
  partial output is retained and cannot be implicitly recovered by another export.
- Original and continued revisions round-trip after deleting the runtime source:
  execution ID stays stable, capture/archive IDs differ, original checkpoint bytes
  remain preserved, and running/completed states are not conflated.
- Unknown → adopted round trips retain one original charged attempt; no new
  transport outcome is invented. Retry preserves first transport failure, final
  completion, both charges and the exact request/context references.
- A copied trusted reader consisting of thirteen pinned producer modules and
  three archive entry-point modules runs outside the original repository/source
  directory with write/network/provider SDK access denied. The first isolated
  probe identified a missing `execution_decisions` dependency; the portable layer
  includes and pins that module, then the probe passes. Archives supply data only.
- A valid source checkpoint larger than 2 MiB round-trips exactly using its
  separate 16 MiB bound. A 288-task/864-question unstarted archive preserves all
  separate task artifacts and stays unsealed.
- Changed capture/projection metadata with updated hashes, byte counts and
  archive identity rejects against regenerated source-bound views. A source run
  counter change with a rehashed archive rejects in unchanged strict 5a replay.
  Missing/extra files, symlink, FIFO, oversized metadata, wrong trusted producer
  pins and a changed lock file reject.
- Five independent subprocess `os._exit(86)` points cover content flush,
  before-marker, temporary marker flush, atomic marker replacement and final
  directory commit. Before replacement the archive rejects; afterward complete
  evidence verifies even though the killed writer returned no acknowledgement.
- Another independent process holds the writer lock before marker publication:
  inspection rejects until release, then the acknowledged archive verifies.
  CLI export executes under network/SDK denial; portable verification also denies
  writes. Existing guard positive controls remain in the complete offline suite.

## Scope and handoff

The stack adds format, fresh exporter and portable reader/CLI with three focused
regression modules. Existing native runners/scorers, strict 5a/5b/5c implementations,
fixture/dependency pins and legacy envelope/MLflow behavior remain unchanged.
The existing Stage 1 CI discovery command includes all new tests.
All 115 evaluation files from the base commit remain byte-identical.

This delivers a durable local archive and trusted-version standalone replay for
**mock** runtime evidence. It is unsigned consistency, not source/writer
authentication, independent human adjudication, semantic/model quality or live
readiness. File/directory barriers and process-crash visibility are checked;
physical power-loss/controller durability and hostile/remote filesystem safety
are not attested. Runtime clock/provider/code attestation flags remain false.

Next after review: runtime archive → existing envelope/registry consumers, then
real local MLflow round trips and write/recovery verification. Reference/score
wiring and separately authorized live capability gates remain later work. #77
stays open/in-progress; these PRs do not complete its full acceptance.
