# Configuration and CLI reference

Use this page when authoring an experiment file or automating a command. For a
short runnable path, start with the
[experiment configuration guide](../guide/experiment-configuration.md).

## `DatasetSpec`

`spec` names columns that are not ordinary model features.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `target` | string | required | Aggregate claim amount column |
| `exposure` | string | required | Positive exposure column used as model and diagnostic weight |
| `claim_count` | string or null | `null` | Aggregate claim-count column; required for frequency-severity |
| `earned_premium` | string or null | `null` | Optional premium column retained in the data contract |
| `time_col` | string or null | `null` | Ordered period used by a temporal split |
| `id_col` | string or null | `null` | Optional policy or row identifier |

`target` and `exposure` must be non-empty. When data loads, every named field
must exist.

## `ExperimentConfig`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `name` | string | `"experiment"` | Stable experiment label used in reports and MLflow |
| `data_path` | string | required | Local or `s3://` Parquet path; relative paths use the process working directory |
| `spec` | `DatasetSpec` | required | Special-column contract |
| `features` | list of strings or null | `null` | Explicit model features; null means every non-special column |
| `preprocessing` | object or null | `null` | Optional binner and grouper settings |
| `split` | `random` or `temporal` | `random` | Outer holdout strategy |
| `test_size` | float | `0.2` | Requested test fraction |
| `random_state` | integer | `42` | Random split seed; estimator seeds remain model parameters |
| `models` | mapping | required, at least one | Stable model name to `ModelSpec` |

Explicit features must exist, be unique, and exclude every named special
column.

## Preprocessing settings

`preprocessing.binner` and `preprocessing.grouper` are parameter mappings.
The workflow injects `exposure_col`, `claim_count_col`, and `target_col` from
`spec`; do not repeat them.

### Binner

| Setting | Type | Default | Meaning |
|---|---|---|---|
| `cols` | list or null | `null` | Numeric columns to bin; null selects numeric non-special columns |
| `strategy` | `quantile` or `tree` | `quantile` | Exposure-balanced cut points or target-aware decision-tree cuts |
| `max_bins` | integer | `8` | Maximum bins per feature |
| `min_exposure` | number or null | `null` | Merge bins below aggregate exposure |
| `min_claims` | number or null | `null` | Merge bins below aggregate claim count |
| `monotonic` | false, true, `increasing`, or `decreasing` | `false` | Isotonic smoothing and adjacent-bin merging |
| `random_state` | integer | `42` | Decision-tree seed |

`min_claims` requires `spec.claim_count`. Missing numeric values get a stable
`Missing` category.

### Grouper

| Setting | Type | Default | Meaning |
|---|---|---|---|
| `cols` | list or null | `null` | Categorical columns to group; null selects non-numeric non-special columns |
| `strategy` | `similarity` or `rare` | `similarity` | Risk-similar grouping or credibility-only rare-level collapse |
| `max_groups` | integer | `10` | Maximum groups for similarity grouping |
| `min_exposure` | number or null | `null` | Collapse levels below aggregate exposure |
| `min_claims` | number or null | `null` | Collapse levels below aggregate claim count |
| `other_label` | string | `"Other"` | Output label for collapsed or unknown levels |

Similarity uses aggregate claim amount divided by aggregate exposure. Ordered
categoricals only merge adjacent levels.

## Model kinds

| `kind` | Required structure | Built estimator |
|---|---|---|
| `glm` | optional `params` | `RiskGLM` |
| `gbm` | optional `params` | `RiskGBM` |
| `frequency_severity` | `frequency` and `severity` sub-specs | `FrequencySeverityModel` |

`ModelSpec.kind` defaults to `glm` and `params` defaults to an empty mapping.
For direct models, `run_experiment` always overwrites `exposure_col` with
`spec.exposure`.

### GLM parameters

| Parameter | Default | Notes |
|---|---|---|
| `family` | `normal` | Set `tweedie`, `poisson`, or `gamma` explicitly for positive pricing responses |
| `link` | `auto` | Use `log` for a multiplicative pricing model or tariff export |
| `tweedie_power` | `null` | Variance power when family is Tweedie; use 1.5 unless portfolio evidence supports another value |
| `alpha` | `0.001` | Regularization strength |
| `l1_ratio` | `0.0` | Elastic-net mixing |
| `fit_intercept` | `true` | Fit an intercept |
| `max_iter` | `100` | Solver iteration limit |
| `gradient_tol` | `null` | Optional glum convergence tolerance |
| `random_state` | `null` | Backend seed |
| `exposure_col` | derived from `spec` | Exposure is removed from features and routed as weight |

### GBM parameters

| Parameter | Default | Notes |
|---|---|---|
| `objective` | `tweedie` | Common alternatives are `poisson`, `gamma`, and `regression` |
| `tweedie_variance_power` | `1.5` | Must satisfy \(1.0 \le p < 2.0\) for Tweedie |
| `num_leaves` | `31` | Maximum leaves per tree |
| `max_depth` | `-1` | No explicit depth limit |
| `learning_rate` | `0.1` | Shrinkage rate |
| `n_estimators` | `100` | Number of trees |
| `min_child_samples` | `20` | Minimum rows in a leaf |
| `subsample` | `1.0` | Row fraction per tree |
| `subsample_freq` | `0` | Subsampling frequency; zero disables it |
| `colsample_bytree` | `1.0` | Feature fraction per tree |
| `reg_alpha` | `0.0` | L1 regularization |
| `reg_lambda` | `0.0` | L2 regularization |
| `monotone_constraints` | `null` | Name mapping or post-exposure sequence with values `-1`, `0`, `1` |
| `random_state` | `null` | Backend seed |
| `n_jobs` | `null` | Backend worker count |
| `verbose` | `-1` | LightGBM verbosity |
| `exposure_col` | derived from `spec` | Exposure is removed from features and routed as weight |

Unknown constructor parameters fail rather than being collected by `**kwargs`.

### Nested frequency-severity YAML

`spec.claim_count` is required. Frequency and severity sub-specs must be direct
`glm` or `gbm` kinds and cannot nest another frequency-severity model.

```yaml
models:
  frequency-severity:
    kind: frequency_severity
    frequency:
      kind: glm
      params:
        family: poisson
        link: log
        alpha: 0.001
    severity:
      kind: glm
      params:
        family: gamma
        link: log
        alpha: 0.001
```

The workflow derives exposure, claim-count, and claim-amount column names from
`spec`. Frequency fits
\(y = \text{claim count}/\text{exposure}\) with exposure weight. Severity fits
only positive-claim rows on mean claim size with claim-count weight.

## Split behavior

| Split | Behavior | Validation |
|---|---|---|
| `random` | Seeded row permutation; rounded `len(data) * test_size` rows go to test | Test must contain between one and `n - 1` rows |
| `temporal` | Sorts `spec.time_col` ascending and places the latest requested fraction in test | `time_col` is required, missing times fail, and equal timestamps never cross the boundary |

Configuration exposes a fraction-based temporal split. For a direct cutoff or
integer test size in Python, use `temporal_split` itself.

!!! warning "Nested selection"

    Tuning creates an inner split of outer training data. The selected candidate
    is refit on all outer training rows, and the outer test is evaluated once.

## Complete YAML shape

```yaml
name: motor-pricing-v1
data_path: examples/synthetic.parquet

spec:
  target: claim_amount
  exposure: exposure
  claim_count: claim_count
  time_col: null
  earned_premium: null
  id_col: null

features:
  - driver_age
  - vehicle_age
  - region
  - vehicle_brand

preprocessing:
  binner:
    cols: [driver_age, vehicle_age]
    strategy: tree
    max_bins: 6
    min_exposure: 50
    min_claims: 5
    monotonic: false
    random_state: 42
  grouper:
    cols: [region, vehicle_brand]
    strategy: similarity
    max_groups: 6
    min_exposure: 50
    min_claims: 5
    other_label: Other

split: random
test_size: 0.2
random_state: 42

models:
  tweedie-glm:
    kind: glm
    params:
      family: tweedie
      link: log
      tweedie_power: 1.5
      alpha: 0.001
      random_state: 42

  tweedie-gbm:
    kind: gbm
    params:
      objective: tweedie
      tweedie_variance_power: 1.5
      n_estimators: 100
      num_leaves: 31
      learning_rate: 0.05
      random_state: 42

  frequency-severity:
    kind: frequency_severity
    frequency:
      kind: glm
      params:
        family: poisson
        link: log
    severity:
      kind: glm
      params:
        family: gamma
        link: log
```

## CLI commands

| Command | Required input | Main options | Output |
|---|---|---|---|
| `azoic profile` | `--data`, `--target`, `--exposure` | `--claim-count`, `--time-col`, `--id-col`, `--out` | Screening table to stdout or CSV |
| `azoic fit` | `--config` | `--out`, `--out-html`, `--quiet` | Model card to stdout, Markdown, and/or HTML |
| `azoic compare` | One or more config paths | `--out`, `--out-html` | Comparison table to stdout/CSV or Plotly dashboard |
| `azoic tune` | `--config` | `--trials 20`, `--calibration-penalty 1.0`, `--out`, `--out-html`, `--quiet` | Best parameters plus model card |
| `azoic export-tariff` | `--config`, `--model`, `--out` | `--distill`, `--recalibrate/--no-recalibrate` | Three-sheet xlsx tariff |

Run `azoic COMMAND --help` for Typer's current option spellings.

## Workflow outputs

| Object | Contents |
|---|---|
| `Run` | Config, SHA-256 data fingerprint, row counts, feature names, and named `ModelResult` objects |
| `ModelResult` | Model kind, effective YAML parameters, diagnostic metrics, and held-out calibration table |
| Metrics | `gini_train`, `gini_test`, `op_ratio_test`, and exposure-weighted Tweedie `deviance_test` at fixed power 1.5 |
| Optional estimator mapping | Returned by `run_experiment(..., return_estimators=True)` |
| Model card | Markdown or minimal standalone HTML |
| Comparison | pandas table or optional Plotly HTML dashboard |
| Tariff | `base_rate`, `factors`, and `mappings` workbook sheets |

## Validation rules

- `ExperimentConfig`, `ModelSpec`, and `PreprocessingSpec` reject extra fields.
- Data must be non-empty; exposure must be positive and finite; target and claim
  count must be non-negative and finite.
- Claim-count and target rows must be zero or positive together.
- Features must exist, be unique, and exclude special columns.
- Temporal splits reject absent or missing time values and keep timestamp ties
  together.
- Tweedie LightGBM power outside \([1.0, 2.0)\) fails.
- Frequency-severity requires both nested sub-specs and `spec.claim_count`.
- Preprocessing credibility by claims requires a claim-count column.
- Model prediction frames may omit outcome columns; fitted workflow pipelines
  supply harmless placeholders and drop them before the final estimator.

::: azoic.cli
