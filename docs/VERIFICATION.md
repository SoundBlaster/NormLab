# Local verification — 2026-10-02

Environment: macOS arm64, Node.js 26.5.0, Lean 4.30.0. No external AI provider was used.

| Evidence                                | Result                                                                                                                        |
| --------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `npm run build`                         | TypeScript strict and Vite production bundle passed                                                                           |
| `npm test`                              | 11 tests passed: domain, negative certificates, stale bindings, persistence, signatures and HTTP workflow                     |
| `npm run test:lean`                     | 2 integration tests passed: all 8 state/bundle combinations accepted; forged unadjusted result independently rejected by Lean |
| Runtime                                 | Local production server at `http://127.0.0.1:4317`                                                                            |
| Open A in browser                       | Verified conditional outcomes: 80/120 months, fine preserved                                                                  |
| Established A in browser                | New immutable snapshot, verified 80 months, signed receipt                                                                    |
| Signature action                        | Ed25519 signature verified against current local issuer                                                                       |
| Reload / process restart                | Saved snapshot and result restored; after verifier identity change a new proof was obtained                                   |
| Dirty draft                             | Previous snapshot result explicitly marked as not covering changed input                                                      |
| Comparison                              | Established: 80 → 60; refuted: 120 → 120; computed finite-domain comparison                                                   |
| Layout                                  | 1440 px desktop and 390 px mobile; document scroll width equals viewport width                                                |
| Browser console after production reload | 0 errors, 0 warnings                                                                                                          |

Browser audit used 15 tool invocations within 13 minutes. Four screenshots were inspected. Two automation selectors initially included decorative symbols excluded from accessible names; corrected selectors succeeded. No application failure was inferred from these locator timeouts. All browser mutations used synthetic inputs. The temporary unsaved test draft was discarded; two saved synthetic snapshots remain in the local, ignored `.data/` directory.

Screenshots are local review artifacts in `.artifacts/` and are not committed. Broad accessibility conformance, other browsers, arbitrary datasets, production isolation, multi-tenant authorization, and a formal comparison receipt were outside this MVP check.

The original prototype's lint was checked separately during intake; it proves neither reference Hypercode conformance nor the runtime properties added by this MVP. Lean receipt guarantees and remaining trusted-base assumptions are described in [MVP.md](MVP.md).
