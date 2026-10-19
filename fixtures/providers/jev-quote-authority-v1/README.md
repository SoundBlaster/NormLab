# Jev quote-authority instruction ablation v1

Issue: https://github.com/SoundBlaster/NormLab/issues/145

## Question and protocol

Can one generic instruction distinguish a copied evidence quote from the typed
proposition being verified? T01 is the primary polarity false-acceptance probe.
T02 (correct denial) and T03 (correct explicit unknown) catch regressions.
T04 keeps parking-specific placement ambiguous; its notice attribution is unchanged.
Expected outcomes: T01 incompatible/reject; T02 and T03 compatible/accept;
T04 indeterminate/review. References remain candidate labels, with prior guided,
nonblind user semantic confirmation; they are not independent whole-task gold.

A copies the previous frozen task bytes. B changes only overall.instructions by
appending instruction-addition.txt after two newlines. State, source, candidates,
criteria, policy, route, requested model and runtime remain identical within pairs.
No rendered proposition, reference answer, abbreviation expansion or extra question
is supplied. The supervisor hashes reviewer-only data but does not read its labels.

Eight fresh requests, Jev only, AB/BA/AB/BA order. One observation per variant/control,
three distinct source texts. Compare within this run, without pooling old observations.
No retries, repair, repeats or escalation;30s operation timeout,300s series deadline.
Stop globally on the first operational/protocol/unknown outcome or drift; remaining
jobs stay not-executed. Semantic disagreement does not stop the planned series.

The user authorized this eight-call series and reconfirmed an external account cap
of$4. Actual remaining balance and pricing are not independently verified; token
usage and unreported costs remain distinct. The earlier twelve-call grant is spent.

## Measures and limits

Record each attempt, returned model, request ID, native probability/confidence,
label/policy outcome, timing and known usage. Primary contrast: T01 rescue.
Record T02/T03 regressions and T04 ambiguity handling individually, including
failures and unknown outcomes. A change on one paired observation does not prove
robustness, statistical significance, general accuracy or a model ranking.

No runtime or pipeline defaults are changed. The frozen plan and one-off supervisor
are evidence for this experiment, not a new framework feature.
