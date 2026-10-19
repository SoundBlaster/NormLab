# Hosted discovery: subject contract

2026-10-19. Related: [#70](https://github.com/SoundBlaster/NormLab/issues/70),
[Medium diagnosis](LUNA_LOW_MEDIUM_COMPARISON_2026-10-19.md).

## Meaning

`subject` is a textual reference to the vehicle or person **about whom/which**
the fragment makes a domain claim. It is not the grammatical subject of the
sentence, the document making the claim, the app name or the payment channel.
`speaker` retains provenance; `aboutEpisode` retains parking-event context.
These fields are distinct. A person ID does not establish driver/owner/payer
roles, and a vehicle must not be invented just to fill the field.

For the source about app/SMS failure and an unsuccessful payment attempt, a
reference to the explicitly discussed person is possible without inventing a car.
The entire technical-failure sentence stays in `quote`. This contract does not
create app/system entities or allow a channel name in `subject`. Text with no
supported person/vehicle referent remains a limitation of the closed vocabulary;
this change does not manufacture a fallback referent.

## Wire/local alignment

Previously the provider schema described `subject` and `aboutEpisode` as arbitrary
strings while local Zod required ID patterns and a maximum128-unit length.
The saved DEV017 response passed that loose provider type and failed locally.

The provider ID-property schemas now come directly from the **same Zod fields**
through `z.toJSONSchema`, with the nested dialect header removed. Patterns and
length bounds are not manually duplicated:

| Field        | Existing local pattern, now also sent to provider | Length bound |
| ------------ | ------------------------------------------------- | ------------ |
| subject      | `^(vehicle\|person)_[1-9][0-9]*$`                 | 128          |
| aboutEpisode | `^episode_[1-9][0-9]*$`                           | 128          |

The hosted discovery prefix explicitly separates thematic reference from grammar
and retains channel names in the literal quote. The shared `inference-prompts.json`
is byte-identical to the historical version: Python Stage1 audits pin that separate
shared contract, so a hosted-only clarification must not change it. Local ID validation is preserved.
There is no automatic repair/rebinding, retry, widened vocabulary or new legal
finding. Other local constraints, speaker trimming, quote verification and
classification rules are unchanged; this is not a claim that every local rule
has become representable in provider JSON Schema.

OpenAI documents `pattern` in the Structured Outputs subset:
[official guide](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).
The exact updated CoreInfra request has **not** been live-tested. A provider
ignoring/rejecting the schema must still fail normally; do not strip constraints
or fall back to another model to hide it.

## Saved-response regression and authored reference

[DEV017 fixture](../fixtures/parking-pilot/hosted-subject-regression/DEV017.json)
contains the exact parsed discovery JSON and original input, with immutable
archive, raw response and output-text SHA256 provenance. It excludes the API
envelope, encrypted reasoning and credentials. The original subject remains
**«Приложение и СМС»**; both the newly emitted provider schema and local parser
reject it before classification.

A separate **authored test reference** uses `person_1` and controlled mock
classifications to exercise the valid shape, exact quote and pending review state.
It is not an edited model result, replay success for the failed capture, human
gold or evidence that a future LLM will choose the correct referent. The actual
failed historical output is never relabelled as passed.

The ID matrix checks19 allowed/forbidden/boundary values against Ajv and the
actual hosted local parsing path. Existing OpenAI/Jev/Decisions hosted tests
remain in the focused verification scope. New provider calls: **0**.

## Versioning and next step

The output shape and default Low effort remain unchanged. Prompts and provider
schema changed, so the computed hosted digest and its regression pin change to
`38752d3eee1f47e199800cd438a94a90656c128f7519f81bb4d48649f198d19d`.
The old low/medium source snapshots, digests, archives and findings are preserved.
See [verification](evidence/hosted-subject-contract-2026-10-19/verification.json)
for actual checks and limits.

This fixes the **wire/local ID constraint mismatch** and clarifies instructions.
It does not prove semantic quality or fix the independent payer-scope,
multi-episode scope or predicate/subject compatibility concerns. Review the change
before a separately agreed live check. A fair new Low/Medium comparison must run
both arms under the same new contract; new Medium versus old Low is a historical
comparison with two changed factors, not an effort-only experiment.
