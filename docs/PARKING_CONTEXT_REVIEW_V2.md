# Parking review v2: context and transport hypotheses

2026-10-19. Implementation slice of [Issue79](https://github.com/SoundBlaster/NormLab/issues/79),
following [narrative context policy](NARRATIVE_CONTEXT_POLICY_V1.md).

## Delivered boundary

The draft stores manual whole-text topic, parking subtype and intent. The application
derives a route: parking review, clarification, another topic, information without
a personal case, or selection of one episode. Mixed episodes must be separated into
a new draft. Selecting a paid-parking topic **does not create `paidRegime` or any
other source statement**. This slice adds no automatic topic classifier, model
prompt change or inference call.

Extraction requires a saved, confirmed context whose route is `parking-review`.
The server enforces this before invoking the extractor; a disabled button is not
the sole gate. A parking topic with `parkingContext=not-established` routes to
clarification, even if its context decision is confirmed. Select the explicit
`parking-unspecified` value when parking is established but payment context is
absent. Out-of-scope and informational texts remain saved and visible.
Manual statement editing remains available while clarification is pending.

## Separate hypothesis review

Select an exact quote in the saved source and choose «Предложить гипотезу о ТС из
выделенного». The hypothesis has its own ID, UTF-16 half-open source range,
episode, rationale, decision and vehicle kind. Its initial kind is `unspecified`:
the application does not replace an implicit vehicle with an automobile.

The user can confirm existence while kind remains unknown, but completing review
requires clarifying the kind or rejecting the hypothesis with a reason. The
`other` kind requires details. Rejection is retained in history; removing an
existing hypothesis from a revision is rejected. There is no automatic hypothesis
generation for «Я припарковался» or «Я стоял на парковке» in this slice: the user
must explicitly propose one. This does not implement semantic enforcement of all
actor/causality examples in the policy packet.

Hypotheses never become source statements, participants, automobile-specific
`placement` findings or legal results automatically. The manual context and
hypotheses are not passed to the model as established facts.

## Revisions and invalidation

1. Save edited context/hypothesis content before confirming it in a later revision.
2. Every metadata change, including confirmation/rejection, resets statement
   decisions and the completeness checklist. It cannot preserve a reviewed status
   or finish review using the same transaction's statement confirmations.
3. Context content edits also reset hypothesis decisions. Successful re-extraction
   preserves the confirmed context but resets hypotheses and statement review.
4. A changed source creates a fresh linked draft with empty context/hypotheses.
   Saved source text and old revisions are retained.

The UI labels unsaved metadata explicitly. Human confirmation records a user's
decision; it is neither independent evidence nor expert adjudication.

## Storage compatibility

New drafts and saves use `normlab.parking-review/v2`. The canonical contract is
[parking-review.ts](../shared/parking-review.ts), with metadata in
[parking-context.ts](../shared/parking-context.ts).

Existing v1 revisions are read without rewriting their bytes or historical
status. Their view has unconfirmed empty metadata and a legacy warning; the next
save creates a v2 revision. A historical v1 `reviewed` record does not authorize
new extraction or a new completed review without the context gate.

## Evidence and limits

[Verification record](evidence/parking-context-review-v2-2026-10-19/verification.json)
separates offline/API checks from a bounded local browser walkthrough. Regression
coverage includes exact anchors, duplicate/removal rejection, two-phase saves,
completion bypass attempts, wrong-topic extraction gates, re-extraction,
invalidation, source reset and byte-preserving legacy reads.

The browser walkthrough created a synthetic «Я припарковался.» draft, selected
its quote, proposed a generic vehicle, selected bicycle, saved, confirmed and
saved again. Reading the resulting local revisions independently confirmed a
pending then confirmed bicycle hypothesis and zero source statements. Context
selection/confirmation and final review completion were covered by API tests,
not this browser walkthrough.

The 15-call browser budget was exhausted. Its screenshot attempt failed because
the requested TB5 path was outside the browser tool's allowed output roots;
**no screenshot was inspected**. Narrow-screen layout, screenshot-based visual
quality, console errors and a complete accessibility audit remain unverified.
The last small unsaved-status label refinement was checked offline after the
walkthrough. No provider calls, deployment, participant sessions or measured
correction time/remaining-error metrics were produced. Issue79's broader
usability acceptance remains open.
