# GPT-6 Luna low comparison — 2026-10-05

[Raw evidence](../experiments/parking-baseline/2026-10-05-codex-gpt-6-luna-low/), [GPT OSS typed baseline](PARKING_TYPED_BASELINE_2026-10-05.md). Four synthetic cases, one response each, no retries, repairs or constrained output. Candidate references are not human-approved semantic truth.

## Method and limits

Requested `gpt-6-luna`, `model_reasoning_effort=low`, Codex CLI 0.156.1. [Official OpenAI documentation](https://developers.openai.com/api/docs/models/gpt-6-luna) lists low reasoning support. CLI events do not attest returned model identity or effective reasoning effort; the observed output reasoning token field is zero in all four cases.

Application instructions and modelInput are byte-equal to the preceding GPT OSS v2 requests. Source revision/digest and contract digest are bound by the same application adapter. The runner reads previous request messages solely to reject input drift; it does not read reference graphs, reviewer notes or previous responses for generation.

Each invocation uses a fresh empty temporary cwd, ephemeral mode, ignored user config/rules, disabled project document loading, shell/multi-agent features disabled and web search disabled. Only the instructions and modelInput are supplied on stdin. All captured item events are agent_message; no tool calls are observed. CLI stderr contains local state database and shell snapshot warnings; they did not prevent completion.

This is a comparison of two execution configurations, not an isolated estimate of model capability. Codex adds built-in instructions and passes application instructions in a user prompt; LM Studio used system/user messages. Token limits, temperature and seed are not matched. Luna CLI reports roughly 21.6–22.0k input tokens, including its surrounding context, versus about 4.4k prompt tokens in the GPT OSS series. Three Luna requests report 7936 cached input tokens. Wall time includes CLI startup/transport and cannot establish model-only speed or cost. No API price or subscription cost is inferred from token counts.

## Observed gates

| Case | GPT OSS wall time | GPT OSS result | Luna wall time | Luna result                                                        |
| ---- | ----------------- | -------------- | -------------- | ------------------------------------------------------------------ |
| P01  | 39.640 s          | Shape rejected | 42.633 s       | Graph rejected: missing role1 entity, two references               |
| P02  | 17.540 s          | Shape rejected | 53.263 s       | Graph rejected: nlinput:payment subject Payment instead of Episode |
| P04  | 33.828 s          | Shape rejected | 48.336 s       | Graph rejected: nlinput:payment subject Payment instead of Episode |
| P09  | 35.192 s          | Shape rejected | 37.347 s       | Structurally valid, unreviewed                                     |

- Both configurations returned JSON in 4/4 cases.
- Luna passed shape and exact quote anchoring in 4/4; GPT OSS stopped at shape in 4/4, so its later gates were not reached.
- Luna passed the complete structural validator in 1/4; GPT OSS in 0/4.
- Mean observed wall time: Luna 45.395 s, GPT OSS 31.550 s. These four samples do not establish general latency or reliability.

## Static semantic review

Raw outputs were inspected without repair or rescoring. This is operator analysis, not expert legal approval, precision/recall measurement or a human-labelled semantic benchmark.

- **P01:** aliases/IDs are neutral and denials of payment, complexity and permits survive. Placement links mostly follow their supplied types. The role1 entity is omitted despite two references to it. The unmapped description says a precise zone designation is absent, even though the source contains M-101. An exact quote does not validate that interpretation.
- **P02:** creates Payment, Session and distinct coverage/placement intervals; preserves payment, departure and major denials. Role references are complete. However payment condition C09 is attached to Payment rather than Episode. Absence of benefits is broadened into disability and special tariff denials, and absence of identifier errors/corrections into faultAndExclusions denial; the source does not establish all of those conclusions.
- **P04:** preserves both vehicles, wrong payment target and correction claim, unlike the preceding GPT OSS output. It duplicates payment condition C09 on a Payment subject. PaidRegime is asserted from a zone mention although the narrative does not explicitly establish the paid regime. The placement interval has no endText despite departure at 12:30. Unknowns are not explicitly captured as gaps.
- **P09:** shape, quotes and graph pass, but the direct denial of payment is demoted to unmappedMentions. There is no opposing denied nlinput:payment assertion, so a consumer examining assertions would miss the conflict. The narrative says “В моей заметке”; the unmapped description's assertion that the author is unidentified is questionable. No Participant/RoleAssignment is created, all attributedTo arrays are empty, and absence of payment corrections is incorrectly treated as a denial of faultAndExclusions while paymentComplexity is absent. Some evidence spans are too narrow to support all facts in their associated statement. The proposal remains unreviewed and must not feed an automatic legal disposition.

## Reproduction and evidence

```bash
rtk proxy npm exec tsx -- scripts/parking-codex-baseline.ts experiments/parking-baseline/new-luna-run
```

Requires authenticated Codex CLI and availability of the requested model. Existing output directories are rejected. Timeout is 240 seconds per case; provider/CLI failure stops the series and leaves later cases unattempted. Exit 0 indicates capture completion, not acceptance. Raw final messages, JSONL events and stderr are preserved separately from validation results; artifact-manifest.json is generated last and is unsigned. run.json records requested arguments, CLI version and runner/adapter digests.

## Decision and next step

Luna is a useful candidate for the next prototype stage: in this series it follows the structural contract more closely and retains more case distinctions. It is not ready for unattended extraction or legal computation. Keep the strict validator and mandatory human confirmation.

Next implement an independent semantic review checklist for opposing assertions, explicit negatives, evidence support, unsupported inference and mandatory unknowns. Reuse P09 as a concrete regression case for “structurally accepted but conflict lost”. Then compare an explicit statement-first extraction contract with application-built graph links. Do not simply repair missing IDs or relax domain checks to improve acceptance counts.
