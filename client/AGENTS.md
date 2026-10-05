# Frontend conventions

- Build new or changed forms with `client/shared/ui/components.tsx`; use `client/shared/ui/tokens.css` for semantic colors, spacing, typography sizes, radii and control dimensions.
- Keep baseline control, button, panel, focus and state styling in `client/shared/ui/ui.css`. Screen CSS defines domain layout and composition; do not copy these foundations into each screen.
- Add a shared component variant when the behavior or appearance is reusable. Preserve native HTML semantics, disabled/read-only behavior, aria props, form submission and React 19 refs.
- Keep primitives small and free of data fetching, storage, model calls or domain decisions. Extract domain editors when their responsibility is clear; avoid generic configuration frameworks for one screen.
- Follow `client/shared/ui/README.md`. Existing M0 and specialized visualization styles migrate incrementally; preserve their behavior while introducing shared primitives.

## Feature-Sliced Design

- Follow `client/ARCHITECTURE.md`. App composes pages; page slices own their workflows; entities own reusable domain contracts; shared contains domain-free infrastructure and UI. Add features/widgets only for actual reuse or independently meaningful blocks.
- Cross-slice imports use `@/layer/slice` public API. Imports inside a slice stay relative. Do not import another page or a higher layer, bypass index.ts, or use wildcard re-exports.
- Browser/server contracts remain canonical in root `shared/`; explicit model adapters expose the required browser subset. Do not import root contracts directly from UI.
- Run `npm run lint` (Oxlint + Steiger) and `npm run check` for architecture changes. The architecture gate fails on warnings; fix the cause rather than disabling boundaries.
