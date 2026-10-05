# Discovery: bounded diagnostic, 2026-10-05

## Purpose

Investigate empty discovery and demo copying before repeating the 40-case run.
Three development probes: explicit payment, explicit non-payment, and opposing
narrator/letter assertions. These are deliberately simple invented texts, not
holdout data or a statistical quality estimate.

## Setup

15 sequential local inference attempts through LM Studio at
`http://127.0.0.1:1234/v1`, model `openai/gpt-oss-20b`, temperature 0, seed 42,
8192 output tokens, no retries, 180-second request timeout. LangExtract 1.7.0.
Every attempted request and available complete SDK response was saved, including
message roles, schema, finish reason, usage and response model identifier.
The model identifier does not pin model weights, quantization or server build.

Artifacts:

- [Initial 12 calls](../experiments/parking-discovery/2026-10-05-ablation-v1/summary.json).
- [Three Russian instruction calls](../experiments/parking-discovery/2026-10-05-russian-v1/summary.json).
- [Runner](../evaluation/diagnose_discovery.py).

The initial run's `workerDigest` was calculated at completion, after formatting
the runner during execution; it is not proof of the exact executing script.
The follow-up captures its executing worker bytes before inference as
`worker.py.snapshot`, with their digest. Saved requests remain the input evidence
for both runs. Responses are unsigned local records.

## Results

The automated gate checks parseable bare JSON, non-empty literal source quotes,
coverage of the expected clauses including negation/letter context, and
`finish_reason=stop`. It does **not** score participant/speaker attribution,
ontology classification, legal sufficiency or gaps.

| Variant | Literal clause gate | Observed failure |
| --- | --- | --- |
| Direct English instruction, text output, no example | 1/3 | One fenced JSON response rejected by strict parsing; one LM Studio engine error |
| Direct English instruction, JSON Schema, no example | 2/3 | Non-payment clause translated to English |
| Direct English instruction, JSON Schema, example | 1/3 | Changed initial letter case; omitted letter context |
| Existing LangExtract discovery | 0/3 | Copied demo statements twice; empty extractions once |
| Direct Russian instruction, JSON Schema, no example | 3/3 | Literal gate passes; speaker attribution still needs repair |

The text-output engine error was HTTP 400 containing a backend `peg-native`
format error. It is separate from empty JSON and demo copying. Available
successful completion responses have `finish_reason=stop`; no token-budget
truncation was observed.

### Remaining attribution issue

For `Я оплатил парковку. В письме написано: я не оплатил парковку.` the Russian
variant preserves both complete sentences, but assigns `speaker=narrator` to
both. It has not explicitly represented the letter as the origin of the
opposing payment claim. A literal-quote pass therefore cannot be reported as
a case without critical errors. This diagnostic does not classify polarity.

## Interpretation

The original narrative reaches the captured LangExtract prompt. The local model
can return literal Russian clauses under a different request formulation, so
the 0/40 baseline is not evidence that this model cannot extract any facts.

The direct English text/schema pair changes response format only. The direct
English schema/example pair adds the example only. The Russian follow-up changes
instruction language and wording together. Direct versus LangExtract changes
message packaging and explicit schema instruction placement together. These
comparisons do not isolate a single root cause or establish a library defect.

In particular, JSON Schema constrains output structure; the observed translation
and attribution errors show it does not establish semantic fidelity.

## Next implementation

1. Create a separately versioned discovery candidate using a direct Russian
   instruction without the demo, keeping source bytes unchanged and exact quote
   validation mandatory.
2. Define and validate narrator versus quoted-claim attribution explicitly.
   Score attribution independently from quote coverage; preserve both claims.
3. Check these development probes, then run the existing 40-case corpus with
   the new version and compare discovery and classification separately.
4. Keep gaps as a separate contract/scorer task. Empty extraction is not a
   successful finding of insufficient information.

No production worker, UI, classification contract or existing baseline was
changed in this diagnostic PR.

## Reproduction

Use new destination directories; existing directories are rejected.

```sh
.tools/parking-evaluation/bin/python evaluation/diagnose_discovery.py \
  experiments/parking-discovery/local-ablation \
  direct-text direct-schema direct-example-schema langextract

.tools/parking-evaluation/bin/python evaluation/diagnose_discovery.py \
  experiments/parking-discovery/local-russian direct-russian-schema
```

Static checks: Ruff check and formatting passed for the new runner. The executed
validation is the 15-call diagnostic above; no broader test suite was run.
