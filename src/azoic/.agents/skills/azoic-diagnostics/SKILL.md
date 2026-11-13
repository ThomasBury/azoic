---
name: azoic-diagnostics
description: Interpret existing Azoic predictions or runs; investigate ranking, calibration, segments and stability without implicitly refitting or recalibrating.
metadata:
  azoic-version: "0.6.2"
---

# Azoic diagnostics

Analyze the supplied results. A diagnosis does not authorize fitting, tuning,
factor changes or recalibration, even when the observed level is wrong.

Before using these recipes, run this in the user's project environment:

```python
from importlib.metadata import version
print(version("azoic"))
```

Compare with `metadata.azoic-version` above. If different or absent, report both
versions and treat these recipes as stale guidance. Stop version-specific execution
until matching guidance/environment is available; never silently upgrade dependencies.

Inputs: existing predicted rates or a trusted saved run, aligned aggregate claims
and exposure, population/split identity, and relevant segments or periods.
Outputs: reproducible tables/plots and a bounded interpretation of ranking, level,
segment credibility and stability. Label development, final-test and production
training evidence separately; explain missing evidence rather than inventing it.

- For existing prediction arrays and the ranking/level distinction, read
  [predictions.md](references/predictions.md).
- For saved runs, segments, time stability and plots, read
  [runs-segments.md](references/runs-segments.md).

Align rows by unique IDs or verified saved positions before comparing predictions.
Azoic `gini`, `op_ratio`, calibration, one-way, double-lift and stability tables
take aggregate claim amounts, predicted rates and exposure weights. Sklearn
deviances instead take `claim_amount / exposure`, rates and exposure weights.
Do not pass rates as Azoic diagnostic claims or aggregate predictions as rates.

Explain Gini alongside calibration and O/P: concentration ranking cannot establish
price adequacy. O/P = sum(claims) / sum(rate × exposure); doubling positive rates
leaves their ranking unchanged and halves O/P. Teacher/student fidelity measures
imitation, not performance against claims. Small segments and unstable periods
limit conclusions; expose their exposure and claims totals. Do not silently drop
missing groups or zero-incumbent cases.

Only load trusted same-environment saved artifacts: pickle executes before version
validation. Reports and predictions must use the existing fitted state. If a
requested comparison needs new fits, identify that separate modelling action.
