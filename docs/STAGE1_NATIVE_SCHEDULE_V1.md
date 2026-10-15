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

## Evidence boundary

These contracts are implemented and checked with local synthetic responses.
They do not establish provider reachability, model quality or paid execution
permission. Candidate-label agreement remains separate from human adjudication.
