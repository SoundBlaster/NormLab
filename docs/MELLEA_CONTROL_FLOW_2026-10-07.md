# Mellea candidate: offline control-flow evidence

Scope: frozen-discovery classification, real Mellea 0.8.0 sampling, Python 3.13.
Generation is fixed DummyBackend output; semantic verdicts are fixtures. This
does not measure LLM/Jev quality, live API availability or the 50% demo target.

## Observed result

The CLI ran all three arms on the same two opposing assertions. Its first
candidate was `{}`; its second contained valid asserted/denied payment proposals.

| Arm | Result | Generation attempts |
| --- | --- | --- |
| baseline | Rejected; no statements exposed | 1 |
| deterministic | Accepted repaired annotation, pending human review | 2 |
| jev | Accepted repaired annotation with fixture pass verdict | 2 |

Eight tests passed with real Mellea installed. They cover source/quote/attribution
binding, full decision contracts, no repair in baseline, one repair, exhausted
budget, semantic failure followed by pass, and terminal uncertainty/error without
another generation, plus cancellation of slow asynchronous generation. In the
existing Python evaluation environment without Mellea, three contract tests
passed and five integration tests skip. CI has a separate job installing Mellea
0.8.0 to exercise all eight.

Mellea's `validation_fn` hook is synchronous, so the candidate overrides async
`Requirement.validate` for thread-backed semantic checks. Mellea 0.8's
DummyBackend omits the generation log required by sampling; the offline fixture
subclass supplies this telemetry without changing the installed framework.

## Reproduce without a key or model

In a separate Python 3.13 environment install `mellea==0.8.0`. Replace `python`
with that interpreter. Do not add these dependencies to the hosted container.

```sh
python -m unittest discover -s evaluation -p test_mellea_candidate.py
python evaluation/run_mellea.py \
  fixtures/parking-pilot/mellea-control-flow/input.json \
  fixtures/parking-pilot/mellea-control-flow/parent.json \
  .artifacts/my-new-mellea-smoke \
  --fixture fixtures/parking-pilot/mellea-control-flow/responses.json
```

The output directory must not exist. Artifacts record candidates, validation
outcomes, definitions, schema/instruction, digests, policies, dependency versions
and latency. Missing usage/cost remain null. These are experimental artifacts,
not the UI's hosted wire format; the existing corpus scorer needs an explicit
format bridge before the paired comparison. No critical-error labels are sent to
the generator or semantic judge.

## Real calls: explicit opt-in, not executed

For a frozen discovery capture and LM Studio running on `127.0.0.1:1234`, use
`--live-local --arms baseline deterministic` instead of `--fixture`.
The backend uses Chat Completions, temperature 0, seed 42 and 8192 max tokens,
without SDK retries. This local candidate does not prove CoreInfra Responses or
Decisions compatibility.

To include the real Jev arm also install a reviewed immutable version of
Jev4Mellea and supply `--live-jev --jev-key-file /absolute/private/key-file`.
This is a TypeSafe supplier key, not a CoreInfra key. Thresholds 0.90/0.10 are
experimental policy, not calibrated accuracy. A transport failure or uncertain
verdict stops the arm; failure feedback repairs annotation, never source text.

Next: freeze the dependency set, add the dataset/scorer bridge with strict
per-case process timeouts, then execute the paired corpus comparison described
in [the approved plan](MELLEA_EVALUATION_PLAN.md).
