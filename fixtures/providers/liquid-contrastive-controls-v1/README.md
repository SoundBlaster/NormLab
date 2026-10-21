# Liquid contrastive controls v1

Prepared at `ee0cee9`; subsequently authorized for twelve attempts by the user.
Actual driver is frozen before inference; results pending. See the
[protocol](../../../docs/LIQUID_D1_CONTRASTIVE_PLAN_2026-10-21.md) and
[ledger #70](https://github.com/SoundBlaster/NormLab/issues/70).

- `tasks/`: twelve exact `state`/`questions` objects, six source-preserving pairs.
- `plan.json`: input/provenance/driver hashes, order and authorized caps.
- `reviewer-only.json`: candidate expectations, never sent to the provider.
- `preparation.json`: offline preparation evidence, not inference or semantic gold.

Original bridge question/conventions are unchanged. P01/P02 change modality,
P03 payer, P04 claimant, P05 unknown stance, P06 raw standing to parking-specific
placement under unresolved PP. Pair suffix a/b is not prompt A/B.

Six authored development sources; no holdout, independent human gold, model
ranking or complete extraction evaluation. P05a/P06b repeat historical T03/T04
controls; no historical label or capture is modified. No secrets are included.
The one-off driver is in `docs/evidence/liquid-contrastive-run-2026-10-21/driver.py`.
