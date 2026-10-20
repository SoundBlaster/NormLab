# One-case hosted schema smoke evidence

User-authorized maximum2-request DEV017 run, no retry. Grant exhausted.
[Full expected/actual report](../../HOSTED_SCHEMA_SMOKE_2026-10-19.md).

- `plan.json` / `authority.json`: protocol and runtime/source bindings frozen
  in commit292d8cc before dispatch. `prepare.mjs` / `driver.mjs`: one-off code.
- `observations.json`: every actual attempt and resource totals.
- `candidate-review.json`: full-output same-agent review; vehicle/causal concerns
  remain, not independent gold or accuracy.
- `replay.json` / `replay.mjs`: full deterministic offline replay except UUID/time.
- `verification.json`: actual checks and archive hash; latest CI distinguished
  from provider/semantic evidence.
- `evidence.zip`:132 manifest-bound payloads plus manifest, including raw responses,
  exact requests/result, frozen bundle/authority, source/dependency snapshots,
  exact input and replay script. ZIP paths/membership/CRC/size/SHA256 and known
  credential-value/token-shape scans passed before publication.

## Offline replay

Extract `evidence.zip` into a new directory, enter it, then with Node26.5.0:

```sh
node repo/docs/evidence/hosted-schema-smoke-2026-10-19/replay.mjs repo runtime capture replay.json
```

No API key required. Global fetch is forbidden; injected transport returns
archived bytes only. `runtime/runtime.mjs` is fully bundled except Node builtins;
no dependency installation. Fresh-extraction replay passed.

Historical Low/Medium archives are unchanged. This archive proves the observed
sample/capture bindings, not signed authenticity, universal credential absence
or provider regex enforcement. Do not rerun live mode or reuse this exhausted
authorization. Further inference needs a separately agreed scope.
