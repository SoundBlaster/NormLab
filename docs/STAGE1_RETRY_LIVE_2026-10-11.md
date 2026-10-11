# Stage 1 retry v2: bounded live comparison — 2026-10-11

## Protocol and authorization

All three arms used CoreInfra from the local runtime with adapter 0.4.0 and the
unchanged pilot request bodies. The v2 runner/scorer from merged PR #57 was used;
no prompts, labels or frozen code were changed. `COREINFRA_API_KEY` was read from
the environment and not stored in artifacts.

The operator reconfirmed sufficient budget, reporting approximately USD 0.015
spent over several days against the previously reported approximately USD 0.10
limit. The permit records that operator declaration, not an independently checked
balance, tariff or supplier enforcement. It authorized **12 total dispatches**,
including retries, and expired 30 minutes after creation. Actual currency cost
remains unknown; the runner enforces attempts, not dollars.

Pilot plan digest:
`f55fe6ccfe8940d8429063fb672e06e7fc37c3c10cb891916b86fbbcd6c286b8`.
The full schedule has 36 semantic jobs, 12 per arm. Its 108-attempt policy ceiling
was not authorized. Every retry retained the exact planned request and used a
fresh client; SDK retries remained zero. Maximum three attempts per job, with
exponential backoff and jitter; no provider/model fallback or prompt repair.

## Transport observations

The runner stopped at **12 dispatches**, `stopReason=budget-exhaustion` (exit 3).
Six attempts returned accepted HTTP 200 outputs, six failed before any recorded
HTTP status with `ConnectError → ConnectError → SSLEOFError`.

| Arm | Started jobs | First-attempt outputs | Final outputs | Recovered jobs | Dispatches | Unknown usage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Jev | 2 | 1/2 | 2/2 | 1 | 3 | 1 |
| Luna Decisions | 2 | 1/2 | 2/2 | 1 | 3 | 1 |
| Luna Low | 3 | 0/3 | 2/3 | 2 | 6 | 4 |

Four of five jobs with eligible first failures recovered. Luna Low's third job
had one failed attempt before the aggregate cap stopped the run; it did **not**
exhaust its three-attempt allowance. Overall, 2/7 started jobs completed on the
first attempt, and 6/7 completed after the allowed retries. Across the full
36-job schedule, six completed, one failed at the cap and 29 were not executed.

The observed TLS failures now affect all three arms, not only Responses. This
does not identify the failing network component or establish a regional-access
restriction. Retries recovered four jobs in this capture; it is not a general
availability estimate or an idempotency guarantee.

## Candidate agreement

Only two contexts completed across all three arms, both from **one authored
story C002**. R003 mutates denied payment into asserted payment; R004 retains
the original denial. Both use repeat 1. Candidate labels are reviewer-authored,
non-independent diagnostic annotations, not expert ground truth.

| Context | Candidate label | Jev final | Decisions final | Luna Low final |
| --- | --- | --- | --- | --- |
| C002 / R003 | incompatible | compatible | incompatible | incompatible |
| C002 / R004 | compatible | compatible | incompatible | compatible |

Final candidate agreement among completed outputs is Jev **1/2**, Decisions
**1/2**, Luna Low **2/2**. First-attempt agreement is respectively 0/1, 1/1 and
undefined (zero outputs). The first/final subsets differ and must not be compared
as an improvement in semantic accuracy. No full case across all scheduled
records/repeats completed. There is no population accuracy, statistical
significance, critical-error-free rate or model ranking from this run.

## Usage and evidence

| Arm | Known input tokens | Known output tokens | Dispatched attempts without usage |
| --- | ---: | ---: | ---: |
| Jev | 3743 | 86 | 1 |
| Luna Decisions | 2178 | 0 | 1 |
| Luna Low | 1930 | 116 | 4 |
| Total | 7851 | 202 | 6 |

Zero reported Decisions output tokens does not establish zero cost. Failed
requests may have been processed/billed; unknown usage remains visible.

Private ignored capture: `.artifacts/stage1-retry-v2-live-20261011-1904/`.
Its index SHA-256 is
`75d95a5b6defbee45ac7f9385ca8171f30c6e98fb5d1452b230a99459d274720`.
SDK-free replay validated the partial capture (exit 3). Predictions were sealed
before this run's scorer loaded labels; the operator had already seen historical
annotations/results, so this is not blinded evaluation. SDK-free scoring passed.
Local hashes are integrity checks, not signatures or trusted timestamps.

The [machine-readable score](../fixtures/parking-pilot/stage1-coreinfra-v1/live-retry-v2-score.json)
retains all 36 planned jobs' denominators, first/final views, attempt counts,
known/unknown usage, paired comparisons and artifact bindings. Historical captures
were not replaced, resumed or merged into this score. Returned model IDs were
`jev-1.13.0` and `gpt-6-luna` for both Luna arms.

## Next experiment

Run a broader, newly authorized matched comparison including C008 and subsequent
contrast families, under an explicit aggregate attempt cap. Preserve the current
partial run. Evaluate agreement on common completed contexts separately from
network recovery; two correlated inputs cannot distinguish strategies reliably.
Use no-inference TLS diagnostics to investigate connectivity independently of
semantic quality rather than spending extra model calls on transport diagnosis.
