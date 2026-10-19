# Manual review UX

2026-10-19. Implementation and follow-up scope for
[Issue #79](https://github.com/SoundBlaster/NormLab/issues/79).

## Why change the form

The bounded agent-operated walkthrough on main `6e531381` found that selecting
a quote created a manual statement with `payment`, `asserted`, and `vehicle_1`
already filled. Those defaults can suggest a meaning that the source does not
support. Raw participant and episode IDs also require knowledge of the storage
format. These are observed interface problems, not findings about model quality.

The example «Оплатить парковку не удалось» reports a failed attempt. It does not
by itself establish that nobody paid. The editor must let the reviewer preserve
that distinction without choosing a legal conclusion for them.

## Stage 1: explicit manual choices

- Capture the selected quote and offsets before editing the new statement.
- Start the semantic fields without a selection. Require an explicit predicate,
  stance, subject, and episode before adding a canonical pending statement.
- Keep “not selected” distinct from the meaningful “unknown” stance or an
  explicitly unresolved reference.
- Present readable reference controls. Preserve existing IDs; an identifier such
  as `person_1` alone is not evidence that this person is the narrator or driver.
- Retain access to custom references and avoid silently rewriting historical
  model or human records.
- Keep the existing save-before-confirm boundary and separate confirmation of
  every statement. Adding a statement is not confirming it.

This slice changes the client editor only. It does not add a canonical entity
registry, stronger server-side semantic validation, automatic interpretation,
autosave, or a legal computation. The saved review schema remains v2.

## Next stages

1. **Draft persistence and decisions.** Autosave edits inside the current draft;
   enable confirmation only after persistence succeeds, and persist the explicit
   confirmation directly. Expose pending, saved and failed states. Preserve
   revision conflicts and invalidation. Editing the source narrative must still
   explicitly create a linked new draft and retain the prior analysis.
2. **Review workspace.** Keep source text near the active card, highlight its
   exact quote, collapse completed cards and show an actionable queue of required
   reviews. Explain which confirmations were invalidated by each edit. Avoid the
   empty second column for a single statement.
3. **Human pilot.** Observe a participant completing a bounded case without
   guidance. Record confusion, corrections, active time and residual errors
   separately from technical completion and model output quality.

These stages are proposals, not implemented capabilities of stage 1. They remain
within Issue #79 until separately scoped implementation work is selected.

## Evidence boundaries

The earlier walkthrough exercised one synthetic case and revision invalidation;
it did not measure human usability or independent semantic accuracy. A source
review, typecheck or build cannot establish visual quality or reduced correction
burden. Report those checks separately from a new browser or human walkthrough.
The broader acceptance criteria of Issue #79 remain open.

Stage 1 was implemented by a scoped Sol 6.1 Medium subagent and reviewed during
integration. The local TypeScript check, Oxlint, Steiger with warnings treated as
errors, changed-file Prettier check, production build and whitespace check passed.
Build output and dependencies were routed to the verified TB5 volume. No new
tests were added or run, and no new browser walkthrough, human session, inference
call or deployment was performed for this slice.

The current hosted extraction need not contain an entity catalog. When no label
is available, the interface uses neutral object/source/episode numbers and puts
the exact stored reference in expandable details. These numbers follow encounter
order in the current data; they are not persistent entity identities. Custom
descriptions remain string references and do not create typed participants.
