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

Boolean and nullable-boolean columns are discrete features: their profiles
include missingness and cardinality, without continuous numeric statistics.

## Learn transparent mappings

`AutoBinner(strategy="tree")` is the default numeric method. Like
[ARFS TreeDiscretizer](https://arfs.readthedocs.io/en/latest/notebooks/preprocessing.html),
it fits one LightGBM regression tree per feature, on pure-premium rates with
exposure weights. `AutoGrouper(strategy="similarity")` uses the same core:
nominal levels use native categorical subset splits; ordered categories use
numeric codes so their groups stay contiguous. Categorical splits retain
LightGBM's L2 regularization (`cat_l2=10`); category smoothing and the per-leaf
row-count floor are disabled. The native Hessian limit guides exposure-aware
splits; final subtree pooling enforces both of Azoic's credibility floors.

Both tree methods require a target. Sibling subtrees collapse if a group falls
below either the aggregate exposure or claim-count floor. Claim counts constrain
groups; they never replace exposure weights. If the whole portfolio cannot meet
a floor, one group remains. Numeric monotonic pooling merges adjacent bins using
observed exposure-weighted target means, including missing rows in their fitted
group. Merging preserves the floors. It does not constrain a downstream model's
predictions after other features enter the model.

Learned numeric tree intervals include their upper edge (`<=`): with edges 30
and 60, the bins are `(-inf, 30]`, `(30, 60]`, and `(60, inf)`. Missing values
follow the fitted tree. Unseen categorical levels follow its missing route and
emit a warning because their risks were never observed. Output vocabularies are
frozen at fit, independent of the scoring batch.

For unsupervised alternatives, `AutoBinner(strategy="quantile")` balances row
count or exposure, uses lower-inclusive intervals (`[30, 60)`), and reserves
`Missing`. `AutoGrouper(strategy="rare")` pools thin levels into `other_label`
(default `Other`), also used for missing and unseen values. Without numeric
edges, every finite value belongs to `(-inf, inf)`.

Native splitting optimizes a training objective; better validation performance
or calibration is not guaranteed. Existing fitted preprocessors must be refitted.

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

Configured exposure and claim-count columns must exist during fitting and
contain finite numeric values. Each exposure must be at least one day (1/366,
with a 0.1% day-count tolerance); claim counts must be non-negative. Omitting
`exposure_col` explicitly selects unweighted binning or unit row weights for
grouping. A present `target_col` takes precedence and contains aggregate claims
when exposure is configured; dividing by exposure gives rates. Otherwise `y`
supplies a strictly one-dimensional rate vector for either tree method.
Supplied outcomes must remain finite after numeric and unit conversion. NaN,
infinity, and entirely missing outcomes raise an error before mappings are
learned, even when the corresponding predictor is missing. Unknown outcomes
cannot count as zero claims.

Transform input must contain every fitted mapping column. DataFrames use their
column names; arrays use `x0`, `x1`, and so on. Switching between named DataFrames
and arrays raises `ValueError` when those names do not match. Keep the fitted
column names when scoring so each learned mapping is applied.

Both transformers expose `mapping_` and accept `set_mapping(...)` after fitting.
An override replaces the entire mapping; omitted columns pass through unchanged.
Keys must name currently binned or grouped columns. Bin edges must be finite,
one-dimensional, and strictly increasing; an empty edge vector selects one bin.
Invalid overrides leave mappings and category vocabularies unchanged.
An unchanged mapping round-trip preserves native routing. Changing a tree
mapping requires keyword-only `missing={column: destination}`: a zero-based
bin index for the binner, or a group label for the grouper. A separate group
for missing values is allowed. Manual numeric edges use the lower-inclusive
convention. For example:

```python
binner = preprocessor.named_steps["binner"]
binner.set_mapping({"driver_age": [30, 60]}, missing={"driver_age": 1})

grouper = preprocessor.named_steps["grouper"]
grouper.set_mapping(
    {"region": {"urban": "urban", "suburban": "urban", "rural": "rural"}},
    missing={"region": "urban"},
)
```

Manual overrides are actuarial decisions: they replace learned floors and
monotonic guarantees. Exported mappings record interval closure and missing
routes. Tariff application remains strict and rejects unseen levels and
nonfinite raw numerics; ordinary pipeline prediction uses the fitted routes.

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
