# Fresh Jev quote-authority rerun with bounded protocol retries

Related to Issue145 and PR156. This is a separately authorized fresh run of the
same eight frozen tasks, AB/BA/AB/BA order, model, endpoint, policy and runtime.
It does not pool or replace the prior partial run. References remain candidate,
not independent gold. Hypothesis and four expected outcomes are unchanged.

The user explicitly approved eight scheduled requests plus at most four retries,
12 total, external account ceiling$4. Allow at most one immediate retry per job,
only after JevProtocolError with a recorded HTTP200 response. Never retry a
semantic mismatch, low confidence, transport/HTTP error, unknown outcome, timeout
or drift. Stop globally on a second failure of the same job or exhausted retry
allowance.30s operation and300s total deadline remain. Preserve every first and
final attempt, unknown usage, failures and unexecuted suffix; no automatic resume.

Primary question: does the instruction rescue the wrong payment assertion?
Report T02/T03 regressions and T04 ambiguity separately. One observation per
variant/control (with failure recovery) cannot establish robustness or population
accuracy. Record first-attempt coverage/agreement and final agreement separately;
do not omit protocol failures from the fixed planned denominator. Native confidence
and category probabilities are retained separately from the caller policy score.

No provider/runtime defaults change. The one-off driver uses the existing CLI;
raw HTTP response bytes remain unavailable. USD and failed-call usage are unknown
unless explicitly reported. The reported$4 ceiling is not a checked balance/price.
