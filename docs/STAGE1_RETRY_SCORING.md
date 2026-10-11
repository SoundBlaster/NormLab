# Retry-aware Stage 1 scoring

`evaluation/score_stage1_retries.py` adds a separate SDK-free evaluator for
`stage1_retry_executor.py` captures. Historical no-retry scorer/executor code,
retry-runner code and existing evidence are unchanged. No provider is constructed,
credential looked up or network call made by this scorer.

## Seal before reading labels

Replay first validates the retry plan and every child attempt. The new seal binds:

- retry-plan digest and parent capture index;
- each child capture digest, child plan digest and ordered turn hashes;
- scorer and shared annotation-helper code hashes.

Only after these bindings are verified does scoring load the original pinned
reviewer-only candidate annotations. It checks bindings again at completion.
Changing a child response and updating its local turn hash cannot reuse an old
seal, even if the outer retry index did not change. Missing/pending child captures
are bound explicitly and remain unknown outcomes. Seals are local integrity
records, not signatures, trusted timestamps or proof of blinded operator access.

## Separate views

Each planned semantic job keeps its full attempt history and two views:

| View | Meaning |
| --- | --- |
| `first` | The first attempt only; subsequent recovery does not erase failure. |
| `final` | The terminal attempt after the permitted retry strategy. |

Each view reports completed outputs, statuses, candidate-label confusion matrix,
matches among completed outputs, matches per all planned jobs and strict complete
case coverage. Unknown outcomes, invalid outputs, model rejection and unused jobs
remain visible. A process-pending attempt has no accepted verdict, even if its
child file contains a response; outer replay's model-drift rejection also excludes
that verdict from scoring.

Per arm, the report additionally records:

- First/final completion among **started jobs**, separately from all planned jobs.
  A job can be started but have zero actual dispatches after a local error; this
  metric measures execution completion, not solely network availability.
- First failures eligible for network retry, recovered jobs, recovery fraction,
  and recovered jobs whose verdict matches the candidate label. Receiving a
  response and matching the annotation are distinct outcomes.
- Started attempts, retries, total/first/retry dispatches. Missing reserved
  attempts count conservatively as potentially dispatched, consistently with replay.
- Known token usage and dispatched attempts with unknown usage. These are not
  a complete bill or currency cost. Failed attempts may still have been charged.
- Scheduled backoff seconds. This does not prove the delay was actually slept;
  mock execution and interruption during backoff make that distinction relevant.

Pairwise tables use the same case/record/repeat keys, separately for first and
final views, showing both planned and jointly completed denominators. First and
final completed subsets may differ: a higher completion rate demonstrates recovery
on this capture, not improved semantic accuracy. Repeats and related candidate
mutations are not independent population samples.

Labels remain **candidate-not-independent**, on authored diagnostic development
cases without a holdout. Population accuracy, statistical significance, product
critical-error-free rate and actual monetary cost remain null. Mock labels are
synthetic and cannot establish provider quality or the demo's quality target.

## CLI

```bash
python3 -B -S evaluation/score_stage1_retries.py \
  fixtures/parking-pilot/stage1-coreinfra-v1/experiment.json \
  .artifacts/your-retry-capture \
  --seal-output .artifacts/your-retry-seal.json

python3 -B -S evaluation/score_stage1_retries.py \
  fixtures/parking-pilot/stage1-coreinfra-v1/experiment.json \
  .artifacts/your-retry-capture --seal .artifacts/your-retry-seal.json \
  --output .artifacts/your-retry-score.json
```

Use new output paths. Exit 0 means valid scoring/sealing, including a partial
capture; examine `stopReason` and coverage. Exit 2 means rejected artifacts.
`--profile corpus` selects corpus lineage, but see the current runner export limit
below; no corpus runtime validation is claimed here.

## Local evidence — 2026-10-11

All nine existing retry mock captures were sealed and scored with Python -B -S,
with `COREINFRA_API_KEY` removed from subprocess environments. Zero external calls.
In the recovery mock, Jev has **11/12 first outputs**, **12/12 final outputs**,
**13 dispatches** and one recovered job. The recovered synthetic verdict disagrees
with its candidate label, illustrating why recovery and annotation agreement must
remain separate. The other two arms each have 12 first/final outputs and 12 calls.

Exhaustion, HTTP failure, malformed output, one-slot/zero-slot caps, pending attempt
and backoff interruption retained their correct denominators. Additional local CLI
checks rejected a different capture's seal and a validly rehashed child mutation
under an unchanged outer index. A missing-child checkpoint counted one unknown
attempt. Evidence is in the fixture summary, with full private reports under
`.artifacts/stage1-retry-scoring-final-v1/`. These are local rehearsals, not a newly
added automatic CI suite or live reliability evidence.

## Known corpus export limitation

The current retry-runner writes its complete parent plan to one JSON artifact.
The corpus plan is about **3.5 MB even before pretty printing**, exceeding its
2 MiB artifact bound. Pilot captures used above fit. A corpus retry run cannot
currently export that plan successfully; the scorer must not be presented as
evidence that the larger end-to-end run works.

Next: introduce a new retry-runner revision with split parent-plan export,
preserving existing source pins and captures, before a broader live comparison.
