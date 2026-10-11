# Stage 1: first three-provider live context — 2026-10-11

Local runtime, adapter 0.4.0; all requests used CoreInfra and
`COREINFRA_API_KEY` from the environment. No key was persisted. This is a partial
pilot, not a completed benchmark. PR #53's five CI jobs were green; there were no
review threads at the start of this attempt.

## Authorization and frozen input

The operator reported approximately **USD 0.10** on the key. Exact remaining
balance, current tariffs and provider-side enforcement were not independently
verified. The local permit records that uncertainty and caps dispatches at **3**,
with no retries, repair, fallback or automatic resume. Currency cost is unknown;
the runner enforces a call cap, not a dollar cap.

Pilot plan digest:
`ac5458e62eca6be1a5d447d1098a7f93cb96f6554dc70a20d2edb554987ba6f2`.
Full schedule remains 36 turns (12 per arm); only its first three were authorized.
All three share C002 / R003 / repeat 1, fresh contexts and identical semantic task.

Source: **«Я не оплатил парковку.»** Candidate's selected payment claim changes
`stance=denied` to **`stance=asserted`**, retaining the original quoted span. Under
the declared conventions, reviewer-only candidate expectation is `incompatible`.
Requests were frozen before submission; no prompt was edited in response to labels.

## Observations

| Arm | HTTP | Verdict | Time | Usage input/output |
| --- | --- | --- | ---: | ---: |
| Jev `jev-1.13.0` | 200 | `compatible` | 2.561 s | 1872 / 43 |
| Luna Decisions `gpt-6-luna` | 200 | `incompatible` | 4.820 s | 1089 / 0 |
| Luna Low `gpt-6-luna` Responses | none recorded | no verdict; `transport-error` | 6.593 s | unknown |

Jev returned confidence 0.79 and probabilities compatible 0.86 / incompatible
0.13 / indeterminate 0.01. Luna Decisions returned confidence 0.24 and probabilities
0.47 / 0.49 / 0.04 respectively. Confidence is provider metadata, not assumed to
equal the winning class probability or establish calibration. Zero reported
Decisions output tokens does not establish zero cost.

Jev request ID: `req_01a12b4403fb72b4a90d961c40490768`.
Decisions request ID: `req_86ccf181dddd44b78dd5b52951023152`.
The Responses failure has no HTTP status, request ID or usage. The current recorder
stores a sanitized error category, not the underlying exception class; its cause
cannot be distinguished from this capture. It does not establish a balance,
regional-access or provider-availability problem. No new request was sent.

The runner stopped on that failure. All remaining 33 turns are `not-executed`.
Exit code 3 denotes a valid partial capture. SDK-free replay succeeded.
The two completed requests report **2961 input / 43 output tokens** in total;
the potentially billed failed request has unknown usage and cost.

## Sealing and scoring

Private ignored capture: `.artifacts/stage1-coreinfra-live-20261011-1400/`.
Capture index SHA-256:
`443adb350f6ab1052bfb6adba0ad0a712b11bfdfa0e2c96d6ac7ad6238d86d40`.
Seal: `.artifacts/stage1-live-prediction-seal-20261011-1400.json`.
SDK-free score: `.artifacts/stage1-live-score-20261011-1400.json`.
The [committed score summary](../fixtures/parking-pilot/stage1-coreinfra-v1/live-three-call-score.json)
retains every planned job without request bodies or credentials.

The scorer verifies this seal before loading labels. The operator inspected the
existing annotation while inference was in progress, after all three request bodies
were already frozen by the plan; this is not a claim of blinded operator evaluation.
Annotations were never included in provider requests.

Jev disagrees with the candidate expectation on the one observed record; Decisions
agrees; ordinary Luna has no semantic result. This is **one matched context**,
not evidence that either provider is generally better. No complete case across
all scheduled records/repeats exists. Do not interpret 0/1 or 1/1 as a population
accuracy estimate, and retain the Responses failure in reliability accounting.

Next: capture a sanitized transport exception class in a new executor revision,
rehearse offline, then explicitly authorize a new live attempt within a confirmed
spending budget. Do not rewrite or resume this historical capture.

## Explicit single Responses repeat — 17:07 Moscow time

The operator explicitly authorized repeating **only Luna Low**. One new direct
httpx2 request used the exact planned J0003 endpoint and body, a fresh client,
30-second per-operation timeout, no redirects/environment proxies and zero
automatic retries. Jev and Decisions were not called again. This separate attempt
does not replace the original failed turn or complete its original capture.

**HTTP 200**, status `completed`, label **`incompatible`**, matching the candidate
expectation. Returned model `gpt-6-luna`, latency **6.053 s**, reported usage
**965 input / 67 output tokens**; currency cost unknown. Response ID:
`resp_0871d4edfdf7be81016acb980fe33c87d2a2c10200d228fea3`.

Private capture: `.artifacts/luna-low-single-repeat-20261011-1406/report.json`.
It binds parent plan/job digests and retains the public normalized response;
authorization headers and encrypted reasoning are excluded. The isolated attempt
could record sanitized exception class names, but no exception occurred. Success
on this attempt leaves the cause of the earlier transport failure undetermined.
It is not part of the sealed original score, and is not a three-arm quality ranking.
