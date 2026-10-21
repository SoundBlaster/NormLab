# Hosted extraction: single-stage RPC

Related task: [hosted recovery #179](https://github.com/SoundBlaster/NormLab/issues/179).
This is the gateway contract for app-owned checkpoints. It does **not** itself
implement durable jobs, partial-result UI or resume; these belong to the app.
The existing `/v1/extract` and local Python extractor remain available.

## Routes and binding

All routes below are internal authenticated JSON POSTs using the existing gateway
Bearer secret, ingress boundary and operator-controlled egress configuration.
The browser cannot choose a provider URL, model, prompt, tool or schema.

| Route                       | Input                                                                               | Result / provider calls                                                                                                           |
| --------------------------- | ----------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `/v1/profile`               | `{}`                                                                                | Protocol, configuration digest, configured discovery/classifier models, batch size 8, maximum 256 fragments. Zero provider calls. |
| `/v1/stage`, discovery      | Narrative, source digest, configuration digest, `stage: discovery`                  | Anchored fragments and private provider evidence. Exactly one provider request on success.                                        |
| `/v1/stage`, classification | Same source/configuration, `stage: classification`, batch index 0–31, 1–8 fragments | Pending model statements, decisions and private provider evidence. Exactly one provider request on success.                       |

Types and strict schemas live in [shared/hosted-stage.ts](../shared/hosted-stage.ts).
The configuration digest covers protocol, selected classifier, used models and
endpoints, and existing prompt/schema/settings digests. Credential rotation is
excluded; changing an alias behind the same provider model name cannot be
detected by this digest. Returned provider model names remain in private evidence.

Source SHA-256, exact unique UTF-16 source anchors, attributes, contiguous fragment
IDs for the given batch, and size bounds are checked before quota consumption or
provider dispatch. A configuration mismatch returns 409. Invalid input returns
400; it never triggers an implicit fallback or a new extraction.

Each successful stage response repeats source/configuration binding and includes
`inputDigest`: SHA-256 of JSON after strict input parsing into deterministic field
order. The app transport checks these fields, stage and batch index before
accepting a result. Evidence can contain floating-point probabilities: checkpoint
file hashes must cover serialized bytes, **not** the integer-only evaluation
artifact canonicalizer. Raw evidence stays private; it is not journal/status UI.

## Execution and limits

- A stage has no internal retry and no automatic provider substitution. A lost
  response does not establish that the provider failed or charged nothing.
- Existing global gateway concurrency is one RPC; active work can temporarily
  return 429 even to a profile request. Health remains available.
- Each dispatched `/v1/stage` consumes **one** unit of
  `NORMLAB_INFERENCE_REQUESTS_PER_HOUR`, including failed provider calls. Profile,
  invalid input and configuration mismatch consume none. Existing `/v1/extract`
  still consumes one unit for its entire legacy run. Both share the same
  process-local hourly counter; a restart resets it. This is not a monetary cap.
- Thus the default 6 permits discovery and up to five classification batches in
  an otherwise unused hourly window. Larger staged jobs must pause and continue
  later or use an explicitly configured operator limit (maximum 60).
- Provider deadline remains 120 seconds; gateway deadline 300 seconds, app
  transport 305 seconds, input 140000 bytes and response 4 MiB. Authentication,
  safe failure forwarding, redirect rejection and egress allowlists are unchanged.

## Checkpoint owner obligations

```mermaid
sequenceDiagram
    participant A as NormLab app (future job owner)
    participant D as App private storage
    participant G as Existing gateway
    participant P as Configured provider
    A->>G: POST /v1/profile
    G-->>A: Config digest and fixed bounds
    A->>D: Persist attempt intent
    A->>G: POST /v1/stage (source + config binding)
    G->>P: One bounded request
    P-->>G: Stage response
    G-->>A: Bound result + private evidence
    A->>D: Commit validated checkpoint before next stage
    Note over A,D: Lost acknowledgement remains unknown; no automatic redispatch
```

The future owner must retain unknown attempts, verify committed checkpoints,
enforce revision/source/configuration compatibility and require explicit Continue
before redispatch. A stage reply is neither a completed extraction nor a legal
decision: statements remain `origin: model`, `decision: pending`. A classification
batch may validly contain no supported predicates. Completeness across all batches
and publication/conflict policy remain app responsibilities.

## Verification

Offline fake-provider coverage in [tests/hosted-stages.test.ts](../tests/hosted-stages.test.ts):
profile binding/credential exclusion, one-call stages and equivalence with legacy
proposals for all three classifiers, floating-point evidence preservation,
source/configuration/anchor/ID/bound tampering, authenticated RPC, quota semantics
and client response binding rejection without retries. No paid requests or deploy
are part of these checks.
