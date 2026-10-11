# CoreInfra live compatibility — 2026-10-11

## Scope and reproducibility

Authorized local runtime check using `COREINFRA_API_KEY` from the environment.
Synthetic English parking narrative from `fixtures/providers/smoke.json`;
SHA-256 `64de735bd08831c42f386ed7d5ccb758696cd4869bf489f1346a940420967bb9`. No real case or personal data was submitted.

Runtime: `mellea-jev-adapter==0.4.0`, Python 3.13, separate
`.tools/provider-evaluation-0.4` environment. Exact SDK dependencies are in each
local capture. Code started at `5b69d60` with the recorder correction below.
This is compatibility evidence, not a benchmark or Stage 1 quality evaluation.

Budget: at most six inference requests; **five dispatched**, no automatic
retries, redirects or fallback. Per-operation HTTP timeout: 30 seconds. Actual
currency cost is unavailable; token usage is reported below. Public Hub/documentation
GET requests were separate from inference and carried no credential or narrative.

## Recorder correction and offline regression

The initial two attempts stopped before dispatch (`calls=0`) with `RequestNotRead`.
The SDK supplied a streaming request body. Recorder now uses `request.read()`
before decoding JSON, preserving the bytes forwarded to the underlying transport.
A regression test exercises both real SDK adapters with mocked HTTP 503:
exactly one request is captured, remaining questions are not executed, the
checkpoint matches the report and the placeholder key is absent. Zero network
calls in that regression. This test is added to the provider CI job.

## TypeSafe System One through CoreInfra

Endpoint: `https://hub.coreinfra.ai/typesafe/api/v1/systemone`.
Requested and returned model: `jev-1.13.0`. Three separate primitive requests.
The story explicitly claims payment and explicitly does not know whether the
payment covered the correct vehicle.

| Primitive | HTTP | Answer | Seconds | Request ID |
| --- | --- | --- | --- | --- |
| payment_claim | 200 | `0.99` | 1.941 | `req_01a12abe945a7506bd04beb013f65249` |
| vehicle_match | 200 | `unknown` | 0.604 | `req_01a12abe96cd70529a1bffc291f61eb0` |
| certainty | 200 | `0.0` | 0.618 | `req_01a12abe992978e08b80dc0d99008f36` |

Choice distribution: `matched=0`, `mismatched=0`, `unknown=1`.
Score distribution on 0–2 certainty rubric: `0=1`, `1=0`, `2=0`.
These answers match the intended synthetic example. Confidence/probabilities
are model output, not verified factual certainty or population accuracy.
Usage across three requests: **1056 input / 80 output tokens**.

## OpenAI Decisions through CoreInfra

Attempted endpoint: `https://hub.coreinfra.ai/codex/api/v1/decisions`.
Requested model: `gpt-6-luna`. The first Noul request returned **HTTP 404**
(`OpenAIHTTPError`) after 1.210 seconds.
Choice and Score were not sent. No response body/error text is persisted.

This does not demonstrate Decisions support at that URL and does not establish
whether another CoreInfra route supports Decisions. The preset remains unverified;
a supplier-confirmed exact URL and model are needed before another attempt.

## Ordinary Luna via OpenAI Responses

Endpoint: `https://hub.coreinfra.ai/codex/api/v1/responses`.
Requested and returned model: `gpt-6-luna`. One direct HTTP request with
`reasoning.effort=low`, `stream=false`, `store=false`, `max_output_tokens=256`
and strict `text.format` JSON Schema. The request asks whether the narrator
claims payment, not whether payment is independently proven.

**HTTP 200**, status `completed`, 3.614 seconds.
Output: `{"payment_claim":true}`; the returned object has exactly the required
boolean field. Response ID: `resp_04c34f50b8e828e7016acb74ca2aa487d2b653a7da1d5f47f1`.
Usage: **71 input / 37 output tokens**, including 21 reasoning tokens.
Encrypted reasoning content was excluded from the normalized local evidence.
This small response proves the checked options worked once; it does not verify
all hosted extraction schemas, long narratives, batching, or semantic quality.

## Evidence and next step

Private local captures (ignored by git):

- `.artifacts/coreinfra-live-2026-10-11-1134/`: initial zero-dispatch failures.
- `.artifacts/coreinfra-live-2026-10-11-1134-r2/coreinfra-jev/report.json`.
- `.artifacts/coreinfra-live-2026-10-11-1134-r2/coreinfra-decisions/report.json`.
- `.artifacts/coreinfra-live-2026-10-11-1134-r2/responses-low/report.json`.

Reports retain synthetic request bodies, normalized answers, HTTP statuses,
usage and runtime metadata, without auth headers or keys. The Responses check
used a direct HTTP request, not the Python Decisions provider or hosted gateway.
No deployment was modified. Total returned usage for successful requests:
**1127 input / 117 output tokens**; the failed Decisions request exposes no usage.

Next: confirm the exact CoreInfra Decisions route, then freeze the selected
Jev/Responses configurations for the bounded Stage 1 live transport. This result
supports continuing with Jev and ordinary Luna; it does not choose the better
classification strategy.

## Follow-up: application API route — 11:50–11:52 UTC

The operator supplied CoreInfra documentation distinguishing:

- Application Chat Completions/Responses: `https://hub.coreinfra.ai/openai/api/v1`.
- Codex agent/model catalogue: `https://hub.coreinfra.ai/codex/api/v1`.
- Both use the hub key with Bearer authorization.

The quoted documentation does not explicitly promise Decisions. We tested that
resource on the application base and it **works on the checked examples**.
The earlier 404 remains valid evidence for the Codex-specific path, not the
application path. The `coreinfra-decisions` preset now uses `/openai/api/v1/decisions`.

### Decisions on the application route

Requested/returned model: `gpt-6-luna`; same fixture and adapter 0.4.0.

| Primitive | HTTP | Answer | Seconds | Request ID |
| --- | --- | --- | --- | --- |
| payment_claim | 200 | `1.0` | 3.002 | `req_d1c611a7eeac460ab58b258ca0ca31aa` |
| certainty | 200 | `0.0` | 1.916 | `req_7138d752320a4293a0bdced6234b7296` |
| vehicle_match | 200 | `unknown` | 1.867 | `req_14f611ca567d4c879776e46dc17f2b38` |

Choice probabilities: `matched=0`, `mismatched=0`, `unknown=1`.
Score probabilities on the original 0–2 rubric: `0=1`, `1=0`, `2=0`.
All completed answers match the intended example. The successful Decisions
requests report **546 input / 0 output tokens** in total. Zero reported output
tokens is provider usage metadata, not proof of free inference.

There were **four Decisions attempts, three successful**. The first Choice
attempt failed before an HTTP status was obtained (`OpenAIProviderError`);
Score in that run was not sent. Score was checked independently; Choice passed
in one new explicit attempt. No automatic retry or provider fallback was used.
The underlying transport exception was not captured for the failed attempt,
so its specific cause remains undiagnosed. Recorder now retains a sanitized
`transportError` class for future failures; regression tests exclude exception
text and credentials. Keep the failed attempt in reliability accounting.

### Responses on the application route

`https://hub.coreinfra.ai/openai/api/v1/responses` returned **HTTP 200** with
`gpt-6-luna`, Low reasoning, `stream=false`, `store=false`, strict JSON Schema
and the same payment-claim question. Status `completed`, 3.301 seconds,
output `{"payment_claim":true}`; exact required boolean shape validated.
Response ID: `resp_085d64a0c2ce6ed2016acb77faccac87d2ae617b42b76a8722`.
Reported usage: **71 input / 42 output**, including 26 reasoning tokens.
Encrypted reasoning content was not retained.

### Follow-up accounting and next step

Five additional inference attempts: four HTTP 200 and one failure without an
HTTP status. Successful usage: **617 input / 42 output tokens**. Failed-attempt
usage and currency cost are unknown. No key was persisted and no deployment
changed. Local captures under `.artifacts/coreinfra-openai-route-2026-10-11-1150/`
retain `decisions`, `decisions-choice-score` (failed), `score`,
`choice-new-attempt` and `responses-low` separately.

The application route is now verified for the checked Decisions primitives and
small Responses schema. Next: freeze these exact endpoints/models/dependencies
for Stage 1, integrate bounded live transport, and compare on matched inputs.
This does not measure general semantic accuracy or production reliability.
