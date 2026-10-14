# Native live boundary v1

Task: [Issue 77](https://github.com/SoundBlaster/NormLab/issues/77).
Base: `901be94d032e68a34a47923803d8ee85ed6e7ef7`.
Additive implementation; existing mock execution and pinned archive consumers stay unchanged.

## Current clock and authorization

`execution_live_gate.py` provides Linux `CLOCK_BOOTTIME`, an opaque SHA-256 host/boot
epoch from `/etc/machine-id` and `/proc/sys/kernel/random/boot_id`, and fresh UTC.
The [Linux manual](https://man7.org/linux/man-pages/man3/clock_gettime.3.html)
and [Python documentation](https://docs.python.org/3.14/library/time.html#time.CLOCK_BOOTTIME)
describe its suspension accounting. Unsupported platforms, missing identities or
missing kernel capability reject; there is no monotonic/UTC-only fallback.
This is a local kernel capability check, not remote attestation or identity authentication.

The pure gate validates the existing live run/plan/permit shapes and requires an
explicit invocation confirmation of `runId`, `planDigest`, `permitDigest`,
`invocationId` and positive `externalCeilingMicros`. A saved permit alone is not
current consent. Confirmation is a trusted local operator assertion, not a signed
identity proof. The external USD ceiling remains operator-asserted; local call/token
ceilings do not enforce currency spending.

Each check binds the current source/units/epoch to the frozen run, rejects clock
regression or backward UTC, checks permit validity and the original deadline,
and applies effective plan/permit reservation ceilings. Request timeout is bounded
by arm timeout, remaining run time and remaining permit validity. The dispatch
boundary must check again after durable reservation and before key lookup/transport.
Checking a serialized sample in offline tests is not evidence of current host capability.

## Native wire transport

`execution_live_http.py` sends the prepared HTTPS route and ordered body using
stdlib `http.client`, with TLS verification and a bounded response. It consults
the gate before connect, before request and between response chunks. It follows
no redirects, reads no environment proxy configuration and performs no retry.
Socket timeouts are bounded by the current gate; DNS and in-flight cancellation
are not guaranteed to terminate exactly at the wall deadline.

The key stays in memory and the Authorization header. Saved responses retain only
public replay fields; provider error/invalid bytes retain a digest and size.
Reasoning blocks are omitted. Payloads containing the actual key or structured
credential fields are discarded. HTTP/network exceptions retain sanitized classes.

`execution_live_wire.py` binds an installed normalizer revision and supports
four existing public protocols. TypeSafe Noul uses `noul`; OpenAI Decisions
predicate uses `probability` and is normalized to Noul. Choice/Score validate
labels, finite distributions and score rubric. Chat/Responses require exactly
one completed text message containing `{"answers": [...]}` in task question order.
Partial, extra or malformed answers reject. The plan must supply that output
contract in its public prompt/schema; the transport never rewrites the request.

These are representative protocol contracts checked with offline fixtures, not
SDK or live interoperability evidence. In particular, existing plan v1's Decisions
request representation is retained; an endpoint with a different request shape
requires a versioned plan/adapter change, not automatic conversion.

## Fresh one-attempt kernel

`execution_live_kernel.py` validates a fresh live-shaped `run.json`, empty
`journal.json`, prepared plan, bound permit and current explicit confirmation.
Input plans must contain the exact installed code/runtime pins and native adapter
revision returned by the offline `requirements` command. Pin generation and
plan construction are separate; no existing plan is silently rewritten.

The output directory is fresh, outside the input tree, and holds an exclusive
writer lock. Input/permit artifacts and intent are written before checkpoint.
The new `normlab.live-checkpoint/v1` atomically publishes run and journal together,
using the existing POSIX durable writer and conservative replay derivation. The
mock schema is never persisted or imported as a live checkpoint. Saved counters
are derived again during read-only inspection; edited or rehashed counters reject.

After a durable reservation, the kernel checks current bounds again, then reads
the named credential environment variable and constructs transport. Exactly one
attempt is permitted by this kernel, regardless of higher plan ceilings. A known
terminal outcome is committed, then the run stops with `operator-stop`; remaining
tasks retain no outcomes. Eligible network failures do not trigger retries here.
Usage is charged once per attempt; missing values stay null, never zero.

Failure after reservation leaves it charged and conservatively unknown unless
the terminal checkpoint was committed. A saved response artifact alone does not
complete it. Inspection grants no execution/resume authority. Current native
archive/MLflow consumers remain mock-only and reject this new live checkpoint.

### CLI

```bash
python3 -B -S evaluation/execution_live_cli.py requirements
python3 -B -S evaluation/execution_live_cli.py inspect live-output
```

The opt-in command expects a separately prepared fresh input tree and run-bound
permit, and all current confirmation values:

```bash
python3 -B -S evaluation/execution_live_cli.py run-once prepared-input fresh-output \
  --confirm-run RUN_UUID --confirm-plan PLAN_DIGEST \
  --confirm-permit PERMIT_DIGEST --confirm-invocation INVOCATION_UUID \
  --confirm-external-ceiling-micros POSITIVE_CONFIRMED_USD_MICROS \
  --key-environment COREINFRA_API_KEY
```

This command sends a potentially billable request on supported Linux hosts.
Examples do not authorize execution. This stack has been checked with synthetic
clocks/fake HTTP only; it has performed zero provider calls. The existing Stage 1
plan builder has not been migrated to this runtime input format yet. On Mac,
`run-once` rejects unsupported clock capability; requirements/inspection are offline.
CLI errors print only exception types, not keys, input prose or provider errors.

The complete scheduler, native resume, live archive/reference/registry consumers
and a separately authorized bounded live smoke remain follow-up slices. Implementing
these primitives does not authorize a provider call or establish model quality.
