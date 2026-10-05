# Frontend architecture

NormLab follows [Feature-Sliced Design](https://feature-sliced.design/docs/reference/layers).
Architecture boundaries are enforced by [Steiger](https://github.com/feature-sliced/steiger) with its recommended FSD rules, import-locality and explicit exports.

```text
client/
  app/                   entrypoint, routes/App.tsx, global styles
  pages/
    reform-lab/           A/B/C workflow, views, transfer
    parking-review/      review workflow, local model, statement editor
    workspace/           legacy M0 decision, packages, comparison, history
  entities/norm/         reusable norm/snapshot/reform contracts and current-analysis policy
  shared/
    api/                 generic JSON transport
    ui/                  tokens and native React primitives
```

## Dependency rules

1. App composes pages; pages can import entities and shared; entities can import shared. A slice cannot import siblings or a higher layer.
2. Import another slice/Shared segment through its `index.ts`, e.g. `@/shared/ui` or `@/entities/norm`. Keep same-slice imports relative. Public APIs list exports explicitly and expose only local modules.
3. Pages contain local workflow state and domain editors. Parking contracts currently have one frontend consumer, so they stay in that page's model. Features and widgets are introduced when reuse or a separate block warrants them.
4. Root `shared/` is the canonical server/browser contract package, not the FSD Shared layer. Only model adapters import it; they expose selected symbols without copying schemas or changing domain semantics.
5. `app/routes/App.tsx` owns navigation and initial bootstrap. Each mounted page keeps its state across navigation; M0 snapshot selection can request navigation through a callback.
6. Shared UI has no domain decisions or API calls. Screen CSS controls layout; token/component styles remain in `shared/ui`.

## Checks

- `npm run lint:architecture` runs Steiger against `client` with `--fail-on-warnings`.
- `npm run lint` runs Oxlint and the architecture gate; CI uses the same command.
- `npm run check` checks aliases/types; `npm run build` checks the production bundle.
- `steiger.config.ts` uses recommended rules without exceptions, plus import-locality and no-wildcard-exports.
- Oxlint `no-restricted-imports` forbids alias/parent-path imports and named re-exports in public `index.ts` files. Steiger 0.7.0 checks import boundaries but does not apply them to named re-exports; this extra gate closes the public API bypass. Internal re-exports are not a substitute for public APIs.
- Oxlint also blocks UI/App imports directly from root `shared/`; contract access goes through model adapters.

Steiger checks the frontend tree. TypeScript/build validate imports from the canonical root contract package; Steiger does not enforce the package's internal server architecture.

## Migration verification (2026-10-05)

`npm run build`, `npm run check`, `npm run lint`, and `npm run format:check` passed locally. Five temporary negative probes were rejected: Shared importing a Page, sibling Page imports, a deep Page import bypassing its public API, a public API re-exporting a higher layer, and UI importing root contracts directly. Probe changes were removed/restored after each run.

Browser Preview opened A/B/C, parking review, and all four M0 views. An unsaved M0 rationale survived a trip to parking and back; the test edit was then cleared. Parking's saved revision and both statement editors remained visible. Production compilation and this bounded walkthrough do not establish a full model/Lean pipeline regression result.
