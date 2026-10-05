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

The pinned Steiger dev dependency currently brings npm audit advisory [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) through braces/micromatch (5 high entries in the dependency chain). npm currently offers a downgrade rather than a patched braces release. This tooling reads repository glob patterns; it is not included in the browser production bundle. Track the upstream fix before accepting externally supplied glob patterns.
