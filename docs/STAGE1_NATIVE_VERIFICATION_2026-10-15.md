# Stage1 native migration: offline verification

Date: 2026-10-15. Issue: [#77](https://github.com/SoundBlaster/NormLab/issues/77).
Contract: [Stage1 native schedule v1](STAGE1_NATIVE_SCHEDULE_V1.md).
Base: `4fb5ef97614954ec7844c82b006b370443fd5976`.

## Scope

Three layers: explicit exact Stage1 wire protocols; pinned source-plan compiler;
shared durable boundary with bounded scheduler, fresh Linux intent binder and CLI.
Historical Stage1 producers and fixtures remain unchanged. Runtime code changes
require regenerated installed-code/runtime pins and fresh authorization.

## Executed checks

- Initial Python 3.14.8 SDK-free discovery: **266/266**, 149.319 seconds.
- After normalization re-derivation and CLI regression additions: Python 3.10.19
  focused suite **33/33**, 10.275 seconds; Python 3.14 kernel/scheduler **21/21**,
  8.331 seconds. Full suite after these changes: **268/268**, 151.586 seconds.
  Lower-layer review correction validation is recorded separately below.
- Compiler checks cover 36-task pilot and 288-task corpus, exact request bodies,
  rotation/source/candidate bindings, complete denominators and bounded artifacts.
- Scheduler success executes all 36 tasks with fake HTTP only. Failure coverage:
  cumulative caps; same-turn retries; max three attempts; certificate/HTTP/output
  terminal failures; model drift; usage excess; deadline/permit expiry; timeout and
  UTC rollback; crash after reservation/dispatch/response; persistent UUID reuse.
- Rehashed result-only mutation and checkpoint mode downgrade reject. Inspector
  and compiler verification/CLI run under network/SDK denial. Compilation allocates
  no run UUID or authority; fake-host binding creates a fresh declared intent.

The first regression run after refactoring failed because automatic import cleanup
removed the kernel's clock/transport re-exports used by the shared boundary. Explicit
re-exports restored the compatibility seam; the existing nine kernel checks passed.
This was an implementation failure found locally, not a provider or network result.

## Limits

All clock/HTTP observations here are synthetic, including live-shaped checkpoints.
No credentials looked up, paid inference, provider reachability, registry writes,
deployment, real Linux dispatch or semantic accuracy evidence. Linux-only current
clock gate remains strict; no Mac monotonic-clock substitute is added.

Native resume, live archive/reference/MLflow consumers and separately authorized
bounded live smoke remain outstanding. Successful retry does not erase uncertain
dispatch/usage on earlier terminal transport failures. Unsigned consistency does
not authenticate provider responses or establish human gold. #77 remains open.
