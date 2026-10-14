# Runtime score-child MLflow verification

Date: 2026-10-14. Task: [Issue 77](https://github.com/SoundBlaster/NormLab/issues/77).
Contract: [score-child import](RUNTIME_SCORE_MLFLOW_V1.md).

## Local evidence

| Check                                                    | Result             |
| -------------------------------------------------------- | ------------------ |
| Complete SDK-free offline suite, Python 3.14.8           | 206/206, 131.474 s |
| Dedicated projection/preparation, Python 3.10.19         | 3/3 + 2/2          |
| Real pinned MLflow 3.16.1 / SQLite suite, Python 3.10.19 | 34/34, 30.628 s    |
| New score-child SDK methods within that suite            | 7/7                |
| Ruff exact CI rules, format, AST, Prettier, whitespace   | Passed locally     |

The existing CI MLflow discovery pattern includes the new SDK test module; the
SDK-free pattern includes projection/preparation tests. No dependency/workflow
change is required. Remote CI and independent review remain separate evidence.

## Outcomes

- Repeated score imports reuse IDs and one metric history item per known count.
  The saved child contains its complete portable archive and canonical score.
  After original archive/runtime/score files are removed, both saved artifacts
  replay-verify and can themselves be re-imported into the same registry.
- New reference revisions create sibling score children under the same capture
  parent and preserve both historical views. Continued captures retain the stable
  execution parent, add capture/score children and do not replace old evidence.
- In-process faults after score run creation, metric commit, artifact upload and
  MLflow finish recover the same child UUID without duplicate histories. These
  exception probes are not independent-process crash or power-loss attestations.
  Successful CLI import/reuse also runs in separate network-denied subprocesses.
- Completed score bytes, metric histories, extra parameters and extra empty
  directories drift reject. Wrong capture-parent binding and boolean substitution
  for a numeric metric reject before score intent creation.
- Dry-run includes the score child without creating storage. Invalid score views
  reject before registry creation. All runtime record comparisons use canonical
  bytes to distinguish booleans from integers.

## Changes and limits

SDK-free projection, additive local importer and real SDK checks form three
delivery layers. Of 133 base evaluation files, 131 remain byte-identical; only
the existing importer and registry are extended. Archive producer pins and saved
score policy/scorer modules remain unchanged. Legacy and score-free runtime
imports remain covered by the 27 existing SDK checks.

The [roadmap](../roadmap.md) now records future universal framework extraction:
finish the #77 full path, verify a second pilot outside law, then extract shared
contracts/control flow behind adapters. Domain ontology/prompts/rubric/scorers
remain in NormLab. Package API, compatibility, evidence migration and license
must be explicit. No package/repository extraction is performed in this slice.

No providers, paid inference, new dependencies, credentials or deployment.
SDK writes use temporary local registries only. Scores remain unsigned mock
selected-question agreement, not authenticated human gold or case accuracy.
Null cost/critical-error-free rate and false semantic/readiness/release flags
remain explicit. Payload bounds include archive, score and projection; imports
near a bound may fail rather than truncate. Multi-record import is resumable,
not atomic. Full Issue77 acceptance remains incomplete.

Next after stack review: runtime paired comparison with explicit compatibility,
partial denominators and separate operational versus selected-reference evidence.
