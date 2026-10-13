# Code quality checks

CI (`.github/workflows/ci.yml`) runs on every pull request to `main`, every push to `main`, and on manual dispatch. Dependabot checks npm and GitHub Actions dependencies weekly. Run the same checks locally:

```sh
npm run format:check
npm run lint
npm run check
npm test
npm run schemas:check
npm run test:lean
npm run build
docker compose config --quiet
```

`npm run format` applies the repository's Prettier settings to application, server, shared, script, test, and build configuration files. `.editorconfig` standardizes UTF-8, LF line endings, final newlines, and indentation in supported editors. The linter is Oxlint with TypeScript-aware rules; warnings fail the command. `npm run check` separately runs TypeScript's strict compiler checks.

## Scoped accessibility and test-runner exceptions

- `typescript/no-floating-promises` is disabled only under `tests/`. The Node.js test runner consumes the promises returned by top-level `test()` registrations; those are test declarations, not detached application work.
- `jsx-a11y/no-noninteractive-tabindex` is disabled only in `client/pages/reform-lab/ui/Views.tsx`. Its three overflowable table regions use `tabIndex={0}` so keyboard users can focus and scroll the tables.
- `jsx-a11y/prefer-tag-over-role` is disabled globally. The application uses ARIA `role="status"` for live status announcements; HTML `output` is intended for a calculation or form result and is not a drop-in semantic replacement for every status message.

## Frontend architecture

`npm run lint` includes `lint:code` (Oxlint) and `lint:architecture` (Steiger). Architecture warnings fail the gate. See [FSD boundaries and ownership](../client/ARCHITECTURE.md).

Steiger 0.7.0 named re-exports do not participate in its import-boundary checks; Oxlint restricts public `index.ts` to local modules. Negative probes confirmed rejection of Shared → Pages, Page → Page, deep public API bypass, higher-layer named re-export in a public API, and UI importing canonical root contracts directly.

### Temporary glob mitigation

As checked on 2026-10-11, Steiger 0.7.0 and braces 3.0.3 are still the latest releases. [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) has no patched braces release. `npm audit` therefore still reports five high entries for this single dev-tool advisory; the production-only audit is clean. Downgrading Steiger is not a complete dependency-chain fix and would change the architecture checker.

`npm run lint:architecture` now installs a temporary guard before loading Steiger. It resolves every braces instance used by Steiger's direct micromatch, globby and fast-glob consumers, then wraps the public parse/compile/expand/stringify entry points. It rejects strings longer than 65536 characters or with more than 64 opening brace/parenthesis delimiters before parsing, and checks AST depth, node count and cycles iteratively before recursive walkers. Counting escaped/quoted delimiters too is conservative: exceptionally elaborate valid patterns can be rejected. Ordinary project globs are unchanged.

This is a scoped runtime mitigation, **not an upstream fix or a clean full audit**. It applies to the guarded npm command, not direct `npx steiger`, other tools, or private braces module imports. It does not make untrusted executable Steiger configuration safe. The dependency remains pinned; unexpected braces versions fail with a request to review/remove the guard. Once a patched release is available, update the dependency chain, remove the guard and rerun `npm run test:architecture` before merging. Do not suppress the advisory or disable FSD rules.

`npm run test:architecture` verifies normal glob behavior, pathological strings/ASTs and five architecture violations in a temporary frontend copy. It runs in the dedicated FSD CI job, as well as the general Node test suite.

GitHub CI runs on pull requests to any base branch, including stacked PRs. The dedicated `FSD architecture` job runs `npm run lint:architecture` with warnings treated as failures; the main verification job runs Oxlint, including public API re-export guards. Push-triggered CI remains limited to `main`.

The project declares npm 10.9.3 (`packageManager`), matching CI's Node 22.19.0 distribution. Regenerate lockfiles with that npm version; npm 11 previously omitted Steiger's optional TypeScript 5.9 peer entry, causing npm 10 clean installation to fail. The application compiler remains TypeScript 7.
