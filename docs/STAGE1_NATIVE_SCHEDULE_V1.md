# Stage 1 native schedule v1

Issue: [#77](https://github.com/SoundBlaster/NormLab/issues/77).

## Wire contracts

Two explicit additive protocol names preserve the existing Stage 1 public bodies:

| Protocol                     | Input                                                                       | Output                                                    |
| ---------------------------- | --------------------------------------------------------------------------- | --------------------------------------------------------- |
| `typesafe-systemone/v1`      | `state`, ordered question dictionary                                        | TypeSafe choice distribution                              |
| `openai-decisions-input/v1`  | `input` string, question/choice arrays                                      | OpenAI named choice distribution                          |
| `openai-responses-stage1/v1` | Independent user input, frozen `text.format`, `store=false`, `stream=false` | Completed message containing exactly `{"overall": label}` |

The latter output maps to one normalized `classification` answer. This changes
neither the historical prompt nor the label semantics. Unknown labels, reordered
choices, changed output schema and partial/refused messages reject. The older
`openai-decisions/v1` state/questions contract and generic Responses answer wrapper
remain separate protocols. No protocol guessing or fallback is performed.

Native normalizer revision `v2-stage1` binds both normalizer and Stage 1 protocol
module bytes. Current installed-code pins change accordingly. Earlier native
plans require regeneration before execution with this installation; old saved
pins are never silently replaced. Historical Stage 1 producers and fixtures stay
byte-for-byte unchanged. A regenerated plan does not inherit execution authority.

## Offline compiler

`execution_stage1_plan.compile_stage1()` runs the existing pinned Stage 1 producer
for `pilot` (36 tasks) or `corpus` (288 tasks). Every source job is retained as a
separate bounded artifact. This avoids putting the full corpus source plan in one
artifact exceeding 2 MiB. A lineage artifact binds source manifest bytes, complete
source-plan digest, metadata, ordered job references and explicit compiler options.

The compiler requires per-arm accepted returned-model lists, an input-token
reservation ceiling and a decision-output reservation ceiling. Responses retains
its original 1024 output-token wire limit. TypeSafe/Decisions have no output-token
limit in the frozen request: their reservation ceilings are accounting limits,
with observed excess stopping further work; they cannot limit provider generation.

All source tasks, exact public bodies, embedded string serialization, ordered
choices, source/candidate artifacts and rotation remain bound. Runtime task case
coordinates include both source case ID and candidate record ID. The original
dispatch/question budget and deadline remain unchanged; retries consume this
shared budget and can leave later tasks unexecuted. No run UUID, clock capability,
permit or credential is allocated/read during compilation.

`verify_stage1()` regenerates the native projection from retained source artifacts.
It rejects changed task metadata, contexts, request bodies and lineage. This is
unsigned consistency evidence; it does not authenticate an attacker-replaced
source manifest or establish human reference labels.

## Evidence boundary

These contracts are implemented and checked with local synthetic responses.
They do not establish provider reachability, model quality or paid execution
permission. Candidate-label agreement remains separate from human adjudication.
