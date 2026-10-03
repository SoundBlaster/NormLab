# Synthetic amendment: unintended N change

This is a reviewed local research fixture, not real legislation. It has the same D16,
finding meanings, liability assumptions, currency and operation order as A/B/C.
The intended change is M = 1/2. The faulty amendment also changes N from 3/4 to 2/3.
All rules are mandatory, apply once, and preserve the other consequence components.

### D-BASE-K1

For supplied group K1, the baseline is 120 prison months and 200000 DEMO fine.

### D-BASE-K2

For supplied group K2, the baseline is 240 prison months and 400000 DEMO fine.

### D-M

For either group, established M requires multiplying prison months by 1/2.

### D-N

For either group, established N requires multiplying prison months by 2/3,
unless excluded by D-X. This additional change is the deliberate fixture error.

### D-X

Established E excludes D-N if N is established. It never excludes D-M.

The exact order is baseline, exclusions, M, N. No rounding is allowed.
At K1/M=false/N=true/E=false, A gives 90 months but D gives 80 months.
At K2/M=false/N=true/E=false, A gives 180 months but D gives 160 months.
Both cases are outside the intended category M and refute preserved-outside.

The older missing-exclusion design variant remains inadmissible in this profile;
it is an admission/decision rejection scenario, not a verified comparison model.
