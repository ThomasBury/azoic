# Data profiling and preprocessing

Pricing preprocessing should make a portfolio easier to reason about without
hiding the learned tariff structure. Azoic separates cheap feature screening
from fitted binning and grouping so an actuary can inspect every mapping.

## Profile before fitting

`profile_features` returns one row per column. `screen_features` adds a
rule-based recommendation; it does not silently drop anything.

```python
from azoic.profile import profile_features, screen_features

profile = profile_features(portfolio)
screening = screen_features(
    profile,
    max_groups=10,
    max_numeric_unique=20,
    missing_drop=0.5,
)

print(screening[["column", "action", "reason"]].to_string(index=False))
```

The actions are `keep`, `bin`, `group`, and `drop`. Treat them as a review
queue: business meaning, availability at quote time, and leakage risk still
override a cardinality heuristic.

## Learn transparent mappings

`AutoBinner` handles numeric features. Quantile binning balances row count or
exposure; tree binning learns target-aware cut points. Credibility floors can
merge bins with insufficient exposure or claim count.

`AutoGrouper` handles categorical features. The `rare` strategy collapses
thin levels; `similarity` combines levels with nearby aggregate pure premium.
Ordered categoricals only merge adjacent levels.

```python
from sklearn.pipeline import Pipeline

from azoic.preprocessing import AutoBinner, AutoGrouper

preprocessor = Pipeline(
    [
        (
            "binner",
            AutoBinner(
                cols=["driver_age", "vehicle_age"],
                strategy="tree",
                max_bins=6,
                min_exposure=50,
                min_claims=5,
                exposure_col="exposure",
                claim_count_col="claim_count",
                target_col="claim_amount",
                random_state=42,
            ),
        ),
        (
            "grouper",
            AutoGrouper(
                cols=["region", "vehicle_brand"],
                strategy="similarity",
                max_groups=6,
                min_exposure=50,
                min_claims=5,
                exposure_col="exposure",
                claim_count_col="claim_count",
                target_col="claim_amount",
            ),
        ),
    ]
)

prepared = preprocessor.fit_transform(portfolio)
print(preprocessor.named_steps["binner"].mapping_)
print(preprocessor.named_steps["grouper"].mapping_)
```

Both transformers expose `mapping_` and accept `set_mapping(...)` when an
approved mapping must replace the fitted one. Missing numeric values get a
stable `Missing` bin. Unknown categorical levels map to `other_label` during
general preprocessing; tariff application is stricter and rejects them.

!!! warning "Fit preprocessing inside the training boundary"

    Tree binning and similarity grouping use outcomes. Fit them only on training
    data. In `run_experiment` they live inside each model pipeline, and outcome
    columns are removed before the final model sees features.

## Configure the same steps in YAML

```yaml
preprocessing:
  binner:
    cols: [driver_age, vehicle_age]
    strategy: tree
    max_bins: 6
    min_exposure: 50
    min_claims: 5
  grouper:
    cols: [region, vehicle_brand]
    strategy: similarity
    max_groups: 6
    min_exposure: 50
    min_claims: 5
```

Do not repeat `exposure_col`, `claim_count_col`, or `target_col` in YAML.
`run_experiment` derives them from `DatasetSpec`.

[Choose and fit models](model-choice.md){ .md-button .md-button--primary }
[See every preprocessing setting](../reference/configuration-cli.md#preprocessing-settings){ .md-button }
