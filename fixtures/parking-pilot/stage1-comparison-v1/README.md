# Matched verifier comparison v1 — offline plan

- [Protocol](../../../docs/STAGE1_COMPARISON_PROTOCOL.md): shared three-way Choice,
  fresh single-candidate context, frozen scheduling, budgets and scoring definitions.
- `experiment.json`: hashes of v2 inputs/review, question, requested provider routes
  and models, execution policy and three separately bounded profiles.
- `plan-summaries.json`: deterministic summaries/hashes of planned requests.

| Profile | Calls / questions | Cases / families | Status |
| --- | ---: | --- | --- |
| pilot | 24 | 2 / 2 | Planned, 0 authorized/executed |
| corpus | 192 | 16 / 13 | Planned, 0 authorized/executed |
| decisions-pilot | 12 | 2 / 2 | Optional plan, 0 authorized/executed |

Sources/candidates are read from the existing immutable v2 dataset without
reviewer-only labels. Only selected safe conventions enter the common task.
Repeated candidates/families are not new independent observations.

```bash
python -S evaluation/plan_stage1_comparison.py fixtures/parking-pilot/stage1-comparison-v1/experiment.json
```

Run from repository root. `--profile corpus`/`--profile decisions-pilot` select a
different plan. `--output NEW_DIR` exports an index plus bounded `jobs/*.json` public planned requests. No provider
SDK, credential lookup, network or live flag. Existing output directories fail.

Current code compiles plans only. Future live executor, captures, choice parsers,
offline scorer and hard runtime budget enforcement remain separate work.
Currency pricing/cap is unknown and no paid calls are authorized by this fixture.
