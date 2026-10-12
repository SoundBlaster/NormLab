# S1.3 offline fixtures v1

Contract and limitations: [S13_OFFLINE_CONTRACT.md](../../../docs/S13_OFFLINE_CONTRACT.md).
Canonical work: [Issue #66](https://github.com/SoundBlaster/NormLab/issues/66).

| File | Role |
| --- | --- |
| `experiment.json` | Public artifact/code hashes, unbound provider, four-arm policies and resource caps; zero authorized live calls |
| `prompts.json` | Frozen whole/local/source-only instructions and Choice alternatives |
| `plan-summary.json` | Label-free compiled plan identity and denominators |
| `examples.json` | Four exact compiled examples (same R010 for A/B/C plus its source focus for D) |
| `reviewer-only.json` | Separate proposed reference labels/rationales; candidate-only, never provider input |
| `mock-capture.json` | 19 handwritten offline response rows, including failures; no model outputs |
| `mock-replay-summary.json` | Frozen scorer summary, including all missing planned jobs |

The compiler reads public inputs from `stage1-audit-v2` without changing them.
Reference labels are read only during scoring, after sealing capture predictions.
All JSON is UTF-8 with byte-preserving Git attributes for stable hashes.

```sh
rtk proxy python3 -B -S evaluation/s13_offline.py check
```

No SDK, credentials or network dispatcher is part of this fixture contract.
Candidate agreement and successful replay are not model quality measurements.
