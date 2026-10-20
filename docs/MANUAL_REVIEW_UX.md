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

## Stage 2: draft persistence and explicit decisions

Valid edits to the current review are saved after a 700 ms pause. Incomplete
manual creation forms, invalid fields and historical revisions are excluded.
Saving does not confirm statements or finish the review. The reviewer still
explicitly confirms or rejects each proposal after its content has been saved;
that decision is then persisted directly, without another Save click.

The client serializes writes and sends the expected revision ID. It adopts the
successful POST response as the saved revision without reopening the source
editor or requiring a second bootstrap request. Source narrative edits and text
selection are preserved. Editing the narrative never rewrites the old draft:
creating a linked new draft still requires the explicit existing action.

Saving/error/pending states distinguish a local decision from a saved one.
A failed or unconfirmed save stops automatic attempts and leaves local changes
in the form. The review POST has a 15-second timeout; a timeout does not prove
that the server rejected the write. Retrying is an explicit action; it retains the expected revision
instead of blindly adopting newer server state. This slice does not merge
conflicting revisions or implement durable offline storage. Unsaved data remains
in the mounted page, not in a browser outbox.

Metadata edits and decisions retain the existing server invalidation rules.
Editing a statement's review rationale also clears its confirmation and the
checklist in the client. Checklist edits may autosave; completing the whole
review remains a separate explicit action after saved prerequisites.

## Next stages

1. **Review workspace.** Keep source text near the active card, highlight its
   exact quote, collapse completed cards and show an actionable queue of required
   reviews. Explain which confirmations were invalidated by each edit. Avoid the
   empty second column for a single statement.
2. **Human pilot.** Observe a participant completing a bounded case without
   guidance. Record confusion, corrections, active time and residual errors
   separately from technical completion and model output quality.

These next stages are proposals, not implemented capabilities. They remain
within Issue #79 until separately scoped implementation work is selected.

## Future direction: annotated source and assembled interpretation

The user proposed a “live” source text: meaningful fragments visibly connected
to the interpretation assembled from them, with explanations. Retain this as
the long-term interaction model. The prototype continues to use selectors while
the review/persistence flow is improved.

A future workspace should connect exact source spans to claims, hypotheses,
participants and unresolved questions. Selecting a fragment should explain what
it supports and what remains uncertain; selecting a claim should reveal its
source. Keep source wording, model proposals and explicit user decisions visibly
distinct. No hypothesis should silently become a fact, and edits must retain the
same invalidation/history rules. This direction does not authorize a new graph
editor, richer ontology or model inference in the current slice.

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

Stage 2 was source-reviewed for persisted-versus-local decisions, invalidation,
single in-flight serialization, timeout and failure retention. Its local
TypeScript, Oxlint, Steiger, changed-file Prettier, production build on TB5 and
whitespace checks passed. No tests were added or run and no runtime/browser
verification of autosave or failure recovery was performed in this slice. These
checks do not establish network recovery behavior or measured UX improvement.
