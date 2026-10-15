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

## Native scheduler

`run-schedule` accepts a fresh compiler-produced plan and bound live intent only.
The one-worker loop uses the same durable boundary as `run-once`. Checkpoint v2
binds `stage1-bounded-schedule/v1`; the inspector still accepts v1 one-attempt
checkpoints and regenerates both versions read-only. Updated installed-code pins
remain mandatory. Mock archive/MLflow consumers still reject these live records.
The inspector also re-derives response-backed normalized outcomes from saved public
response projections and rejects result-only changes even after hashes are updated.
Raw-response digests are retained; missing raw bytes cannot be reconstructed or
authenticated by this unsigned reader.

Before every reservation the gate uses the actual scheduled task's arm, caps and
timeout. One run UUID, invocation, original deadline, permit and aggregate budget
cover the whole schedule. Each retry retains its task/turn and gets the next
attempt ordinal. Original per-attempt timeout decreases across transport callbacks;
it is not restarted for each response chunk. Kernel BOOTTIME and UTC continuity
are checked across reservations, publication, waits and transport callbacks.

The frozen retry policy allows at most three attempts for terminal transient
transport failures, with deterministic lower-bound delays of 1 and 2 seconds.
HTTP errors (including 429/503), certificate failures, invalid output, refusals
and model rejection stop the suffix. Returned-model drift within an arm rejects
even when the new model belongs to its explicit acceptance list. Known usage above
a per-request reservation ceiling stops further work; absent usage stays unknown.

A saved reservation without a committed terminal outcome remains unknown and
cannot be automatically retried or resumed. The persistent local UUID authority
also rejects using its immutable input again in a different output directory.
This requires preserving that authority directory in containers. A terminal
transport failure may have unknown dispatch/usage despite being eligible for the
explicit retry policy; all such attempts remain visible and prevent reporting an
exact observed inference total. No exactly-once provider execution is promised.

Budget exhaustion and deadline expiry append their corresponding stop events.
Permit expiry between known attempts uses the existing `operator-stop` reason;
saved permit and event UTC expose expiry. A gate failure after reservation leaves
the reservation unknown. Inspection itself reports zero invoked/authorized calls.

## CLI workflow

Compile and bind on the Linux execution host, using the same Python installation
and code revision as dispatch. Mac supports compilation/inspection only; a plan
compiled on Mac normally has different runtime pins and must be rebuilt on Linux.

```bash
python3 -B -S evaluation/execution_live_cli.py compile-stage1 \
  fixtures/parking-pilot/stage1-coreinfra-v1/experiment.json \
  /private/run-parent/compiled --profile pilot --options /private/options.json
python3 -B -S evaluation/execution_live_cli.py verify-stage1 /private/run-parent/compiled
```

`options.json` contains public configuration, never credentials:

```json
{
  "acceptedModels": {
    "jev-coreinfra": ["jev-1.13.0"],
    "luna-decisions-coreinfra": ["gpt-6-luna"],
    "luna-low-coreinfra": ["gpt-6-luna"]
  },
  "inputTokenCap": 20000,
  "decisionOutputTokenCap": 1024
}
```

These example model strings are requested-model spellings, not a newly confirmed
catalog of returned aliases. The operator must explicitly select acceptance sets.
Compiler output is a zero-authority dry-run, not permission to spend.

`bind-stage1 compiled input --authorization authorization.json` allocates a fresh
UUID and Linux clock origin without dispatch. Its authorization object has exactly:

```text
schema = normlab.stage1-native-authorization/v1
planDigest = exact compiled plan digest
caps = {dispatches, questions, inputTokens, outputTokens} integer ceilings
expiresAt = UTC with microseconds
authorization = {operatorId, authorizationRef: SHA-256, authorizedAt: UTC}
externalSpending = {currency: USD, ceilingMicros: positive integer,
                   confirmationRef: SHA-256, provenance: operator-asserted}
```

The externally enforced spending limit must actually exist; the local declaration
does not enforce a dollar ceiling. Binding returns the exact confirmation values.
The separate `run-schedule input output` command requires `--confirm-run`,
`--confirm-plan`, `--confirm-permit`, `--confirm-invocation` and
`--confirm-external-ceiling-micros`. Source manifest environment references select
credentials only after durable attempt reservation. Credentials are not CLI args,
saved artifacts or prompts. No SDK, network, key read or run authority is needed
for `verify-stage1`; `inspect output` is also read-only.

Only a separately authorized bounded live invocation establishes provider evidence.

## Evidence boundary

These contracts are implemented and checked with local synthetic responses.
They do not establish provider reachability, model quality or paid execution
permission. Candidate-label agreement remains separate from human adjudication.
