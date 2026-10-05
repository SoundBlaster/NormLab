# Frontend conventions

- Build new or changed forms with `client/ui/components.tsx`; use `client/ui/tokens.css` for semantic colors, spacing, typography sizes, radii and control dimensions.
- Keep baseline control, button, panel, focus and state styling in `client/ui/ui.css`. Screen CSS defines domain layout and composition; do not copy these foundations into each screen.
- Add a shared component variant when the behavior or appearance is reusable. Preserve native HTML semantics, disabled/read-only behavior, aria props, form submission and React 19 refs.
- Keep primitives small and free of data fetching, storage, model calls or domain decisions. Extract domain editors when their responsibility is clear; avoid generic configuration frameworks for one screen.
- Follow `client/ui/README.md`. Existing M0 and specialized visualization styles migrate incrementally; preserve their behavior while introducing shared primitives.
