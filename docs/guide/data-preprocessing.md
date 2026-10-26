# Data profiling and preprocessing

!!! note "Unreleased checkout documentation"

    This page describes the current source checkout; some APIs differ from the
    published 0.5.0 package. For a release-compatible journey, start with the
    [first model](../getting-started/first-model.md). See
    [installation](../getting-started/installation.md) for the version boundary.

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

### Keep approved mappings fixed through refits

Set `fixed` on `AutoBinner` / `AutoGrouper`, or inside their YAML settings.
Listed features use those mappings during every fit; other selected features
still learn on training rows. Numeric edges must be finite and strictly
increasing. Declare `closure: left` for lower-inclusive intervals or `right`
for upper-inclusive intervals (`<=`). Missing numeric values require an existing
zero-based bin destination; index `len(edges) + 1` selects a separate `Missing`
bin, preserving the quantile convention. Empty edges mean one interval; route
missing to 0 or to a separate `Missing` bin at index 1.

Categorical mappings use a list of `level` / `group` records, preserving scalar
types: integer `1` and string `"1"` are different levels. Equal numeric/boolean
aliases such as `1` and `true` are rejected. Both `missing` and `unseen` group
destinations are required and may differ. Destination-only groups enter the
output vocabulary; if training supplies no observations there, fitted factors
have no direct experience for that group.

```yaml
preprocessing:
  binner:
    cols: [driver_age]
    fixed:
      driver_age:
        edges: [30, 60]
        closure: left
        missing: 1
  grouper:
    cols: [region]
    fixed:
      region:
        groups:
          - {level: urban, group: metro}
          - {level: suburban, group: metro}
          - {level: rural, group: other}
        missing: other
        unseen: metro
```

Fixed mappings are explicit actuarial decisions: learned credibility floors and
monotonic guarantees do not apply to those features. Outcome and exposure
validation still applies. Tree methods need outcomes only for features whose
mappings are learned.

To change a boundary, copy the configuration, change its fixed specification and
call `run_experiment` again. Keep the development portfolio and split settings
the same. This creates a new candidate and fits downstream model parameters on
the revised feature space. Keep the previous Run and estimators for comparison.
Editing a live pipeline with `set_mapping` does not refit its model; use fixed
configuration plus a new fit for a controlled candidate revision.

### Learn mappings from training data

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
