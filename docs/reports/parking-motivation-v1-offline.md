# Parking motivation v1: offline preparation

Date: 2026-10-28. Task: https://github.com/SoundBlaster/NormLab/issues/239.
This is a contract/dataset preparation receipt, not a model experiment result.

| Frozen item                                    | Value                                                    |
| ---------------------------------------------- | -------------------------------------------------------- |
| Ontology compiler release                      | 0.1.1, source `21e4cb32ed042e629e72b708b8b086fb32d4cebc` |
| Generic vocabulary                             | events-core 0.2.0, motivation-core 0.1.0 (draft)         |
| Optional parking package                       | normlab.parking-motivation 0.1.0 (draft)                 |
| Extraction profile                             | normlab.parking-motivation-proposal/v1                   |
| Dataset                                        | motivation-v1, authored development version 1.0.0        |
| Sources / reference hypotheses / support edges | 24 / 26 / 27                                             |
| Verifier reference labels                      | compatible 11, incompatible 10, requires_review 3        |
| Model/provider calls                           | 0                                                        |

Exact source-byte digests:

- inputs.json: `f259df8828545184b1596d4ecbd5790dad7f7401010ae4be6e76e9539f9fcc2d`
- reviewer-only.json: `5d1ba3f53e5727ad766646aafcfa9f34a0c811766d3febe5cb1238602cb341d8`
- exported plan: `8a1fc3289474cc17a07cf2f7c453def589def27570aea3d0ee72f9755730c063`

Local verification:

- Native `ontologyc compile` succeeded. A second compilation into a separate
  verified TB5 temporary directory matched all ten committed generated files
  byte for byte. The manifest checker verifies upstream/input/output hashes and
  resolves imported relation endpoints against the pinned normalized IRs.
- `npm run parking:motivation:check` passed all 24 references.
- `tsx --test tests/parking-motivation.test.ts`: 14/14 passed. Controls cover
  exact/repeated/UTF-16 quotes, letter speakers, unresolved/nonhuman actors,
  negative/contested support, forged authority/physical/norm fields, scope and
  request mutation, duplicate captures, exclusive exports and missing/error
  accounting. A deliberately wrong motive summary with correct anchors confirms
  that the edge metric makes no semantic correctness claim.
- `npm run check`, `npm run lint:code`, `npm run format:check` passed.
- CLI export → reference self-replay → scoring completed: 24 anchored captures,
  27 matched reference edges, no extra/missing edges. This is a self-consistency
  control using the authored references, **not model performance**; semantic
  accuracy remains unmeasured.
- `ruff check --select E4,E7,E9,F,I` and `ruff format --check` passed for the new
  SDK-free Python checker.
- Offline export succeeded. Python 3.13 with `-B -S` accepted all 24 exported
  Choice tasks and explicit routing policies through the existing consumers.
  `categorical_smoke.py` produced a D1 dry-run plan (`calls=0`, `plannedCalls=1`)
  for M01. No credentials, SDK execution or network inference were needed.

Hosted CI belongs to the exact PR revision and is reported separately in the
Issue/PR. No GUI/deployment/Lean integration or live model quality was measured.
The references are same-agent authored, with no independent semantic adjudication.
The generic motive-to-graph policies remain manual; this source-only proposal
profile admits no physical snapshots, Delta or legal result.

Next: review the authored expectations, then freeze a separately authorized
bounded comparison with exact generator/verifier providers, versions, settings,
call/time/cost caps and complete attempt accounting. Do not interpret this
preparation as acceptance of current-model quality.
