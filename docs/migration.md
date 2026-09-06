# Migration to Azoic 0.4

Azoic 0.4 is the package and CLI rename from `riskforge`. The migration is
deliberately direct: update source configuration, refit serialized estimators,
and verify the same held-out workflow.

## Required changes

- Replace `riskforge` imports with `azoic`.
- Replace `riskforge` commands with `azoic`.
- Refit pickle or joblib estimators because their old module paths no longer
  resolve.
- Update automation to the canonical documentation and tutorial URLs.

No compatibility package or CLI alias is provided.

## Removed stratified split helper

`azoic.validation.stratified_random_split` has been removed. Replace calls with
scikit-learn's `StratifiedShuffleSplit` directly to retain positional indices:

```python
import numpy as np
from sklearn.model_selection import StratifiedShuffleSplit

splitter = StratifiedShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
train_idx, test_idx = next(splitter.split(np.zeros(len(strata)), strata))
```

Keep your existing `strata`, `test_size`, and `random_state` values. Select rows
with `df.iloc[train_idx]` and `df.iloc[test_idx]`. Validation errors now come
from scikit-learn; code matching the helper's error messages must be updated.
`make_strata` and `temporal_split` remain available.

## Corrected tariff preprocessing

`AutoBinner` interval labels now describe the existing lower-inclusive,
upper-exclusive assignments. For example, `(-inf, 30.0]` becomes
`(-inf, 30.0)` and `(30.0, 60.0]` becomes `[30.0, 60.0)`. Observation membership
has not changed, but fitted categorical vocabularies contain the old strings.
Refit preprocessing and downstream models and regenerate their tariff workbooks
together; do not mix an old estimator or workbook with corrected labels.

Nominal `AutoGrouper(strategy="similarity")` now merges the closest adjacent
risks after sorting levels by aggregate pure premium. Previously, enforcing the
group limit pooled the highest-risk tail regardless of risk distance. This
correction can change the learned groups and predictions. Refit affected models
and regenerate held-out metrics, charts, and exported tariffs on the original
train/test boundary. Earlier evaluation results do not describe the refitted
models.

[Install Azoic 0.4](getting-started/installation.md){ .md-button .md-button--primary }
[Run a first model](getting-started/first-model.md){ .md-button }
[Review configuration and CLI](reference/configuration-cli.md){ .md-button }
