---
name: azoic-modelling
description: Prepare development data, configure preprocessing, fit or tune Azoic pure-premium candidates, and save runs when modelling is requested.
metadata:
  azoic-version: "0.6.2"
---

# Azoic modelling

Use the user's modelling request to determine which candidates to fit. Inspecting
existing predictions alone does not call for training.

Before using these recipes, run this in the user's project environment:

```python
from importlib.metadata import version
print(version("azoic"))
```

Compare with `metadata.azoic-version` above. If different or absent, report both
versions and treat these recipes as stale guidance. Stop version-specific execution
until matching guidance/environment is available; never silently upgrade dependencies.

Inputs: portfolio and column roles, explicit predictors, exposure/claim basis,
predeclared final IDs (or an already separated development portfolio), requested
models and output location. Clarify missing choices that affect the experiment.
Outputs: validated development configuration, fitted candidates, development
diagnostics, saved run and preserved membership/environment evidence as requested.

- For separation, fitting and saving, read [development.md](references/development.md).
- For mapping choices, fixed mappings, frequency/severity or tuning, read
  [preprocessing-tuning.md](references/preprocessing-tuning.md).

Fit rate targets (`claim_amount / exposure`) with exposure weights. Frequency uses
`claim_count / exposure`; severity uses positive-claim rows, amount/count and count
weights inside `FrequencySeverityModel`. Special columns travel in X, not custom
fit kwargs. Portfolio exposures are years, at least one day (1/366); do not repair
invalid outcomes or apply claim caps without an explicit data decision.

Learn preprocessing and select parameters within development training rows.
Workflow/tuning `test` metrics are development validation. Preserve final membership
before experimentation and keep final data outside fitting, tuning and selection.
Exclude IDs, outcomes, protected/excluded columns and incumbent rates from predictors.
Record upstream basis assumptions; metadata does not transform claims.

Pair Gini with calibration and O/P. Azoic diagnostic tables take aggregate claims
and predicted rates; sklearn deviances take observed rates and exposure weights.
Save the run plus fitted estimator dictionary; keep source data and environment
separately. Pickle artifacts require trust and matching Python/dependency versions.
