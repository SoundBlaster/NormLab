# Code quality checks

Run the same checks locally that are required by `.github/workflows/ci.yml`:

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
- `jsx-a11y/no-noninteractive-tabindex` is disabled only in `client/lab/Views.tsx`. Its three overflowable table regions use `tabIndex={0}` so keyboard users can focus and scroll the tables.
- `jsx-a11y/prefer-tag-over-role` is disabled globally. The application uses ARIA `role="status"` for live status announcements; HTML `output` is intended for a calculation or form result and is not a drop-in semantic replacement for every status message.
