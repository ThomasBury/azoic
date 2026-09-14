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
| `time_col` | string or null | `null` | Ordered period used by a temporal split |
| `protected_cols` | list of strings | `[]` | Review-only subgroup columns retained for held-out calibration and excluded from features |

`target`, `exposure`, and every protected-column name must be non-empty.
`protected_cols` must be unique and cannot overlap target, exposure, claim count,
or time. When data loads, every named field must exist.

## `ExperimentConfig`

| Field | Type | Default | Meaning |
|---|---|---|---|
| `name` | string | `"experiment"` | Stable experiment label used in reports and MLflow |
| `data_path` | string | required | Local or `s3://` Parquet path; relative paths resolve from the config file's directory |
| `spec` | `DatasetSpec` | required | Special-column contract |
| `features` | list of strings or null | `null` | Explicit model features; null means every non-special column |
| `preprocessing` | object or null | `null` | Optional binner and grouper settings |
| `split` | `random` or `temporal` | `random` | Outer holdout strategy |
| `test_size` | float | `0.2` | Requested test fraction |
| `random_state` | integer | `42` | Random split seed; estimator seeds remain model parameters |
| `models` | mapping | required, at least one | Stable model name to `ModelSpec` |
| `tuning` | `TuningSpec` or null | `null` | Optional trial settings and per-model scalar search spaces |

Explicit features must exist, be unique, and exclude every named special
column, including protected columns. Automatic feature discovery excludes them
for the same reason.

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

## Tuning settings

`TuningSpec` is optional. Its complete YAML shape is:

```yaml
tuning:
  n_trials: 30
  calibration_penalty: 2.0
  search_space:
    tweedie-glm:
      alpha:
        type: float
        low: 1.0e-6
        high: 0.1
        log: true
      l1_ratio:
        type: float
        low: 0.0
        high: 1.0
    tweedie-gbm:
      num_leaves:
        type: int
        low: 8
        high: 64
        step: 8
      max_depth:
        type: categorical
        choices: [-1, 4, 6]
```

| Field | Type | Default | Validation |
|---|---|---|---|
| `n_trials` | integer | `20` | At least one |
| `calibration_penalty` | finite float | `1.0` | Non-negative |
| `search_space` | model-name mapping | `{}` | Names must exist in `models`; each supplied model space must be non-empty |

| Distribution | Required fields | Optional fields | Validation |
|---|---|---|---|
| `float` | finite `low`, finite `high` | positive finite `step`, `log: true` | `low <= high`; `step` and `log` are mutually exclusive; logarithmic bounds are positive |
| `int` | integer `low`, integer `high` | positive integer `step` (default `1`), `log: true` | `low <= high`; logarithmic sampling requires positive bounds and `step: 1` |
| `categorical` | non-empty `choices` | none | Each choice is null, boolean, integer, finite float, or string |

A custom model entry replaces that model's built-in search space. It does not
merge with the defaults. GLM or GBM siblings without a custom entry keep their
existing built-in spaces exactly:

| Model kind | Parameter | Distribution | Bounds |
|---|---|---|---|
| `glm` | `alpha` | float, log | 1e-6 to 1.0 |
| `glm` | `l1_ratio` | float | 0.0 to 1.0 |
| `gbm` | `num_leaves` | int | 4 to 64 |
| `gbm` | `learning_rate` | float, log | 1e-3 to 0.3 |
| `gbm` | `n_estimators` | int | 20 to 300 |
| `gbm` | `min_child_samples` | int | 1 to 100 |
| `gbm` | `reg_alpha` | float, log | 1e-8 to 10.0 |
| `gbm` | `reg_lambda` | float, log | 1e-8 to 10.0 |

Search-space parameters must be exposed by that model kind's estimator.
Unknown model names, unsupported parameters, frequency-severity spaces, empty
spaces, empty choices, invalid distributions, and extra fields fail validation.
The fixed identity, routing, and seed parameters `family`, `link`,
`objective`, `tweedie_power`, `tweedie_variance_power`, `exposure_col`,
and `random_state` cannot appear in a search space.

Explicit Python `n_trials=` and `calibration_penalty=` arguments have highest
precedence. CLI `--trials` and `--calibration-penalty` supply those explicit
arguments. Omitted arguments defer first to `tuning`, then to 20 and 1.0.
The sampler's separate `random_state=42` API is unchanged.

## Split behavior

| Split | Behavior | Validation |
|---|---|---|
| `random` | Seeded row permutation; rounded `len(data) * test_size` rows go to test | Test must contain between one and `n - 1` rows |
| `temporal` | Sorts `spec.time_col` ascending and places the latest requested fraction in test | `time_col` is required, missing times fail, and equal timestamps never cross the boundary |

Configuration exposes a fraction-based temporal split. For a direct cutoff or
integer test size in Python, use `temporal_split` itself.

## Random seeds

Three independent seeds control an experiment; set each where it belongs.

| Seed | Default | Scope |
|---|---|---|
| `ExperimentConfig.random_state` | `42` | Outer split permutation only |
| Model `random_state` parameter | Backend default (unset) | Estimator fitting; a per-model constructor parameter, never tunable |
| `tune_experiment(random_state=)` | `42` | Optuna sampler; model index `i` samples with `TPESampler(seed=random_state + i)` |

!!! warning "Nested selection"

    Tuning creates an inner split of outer training data. The selected candidate
    is refit on all outer training rows, and the outer test is evaluated once.
    Custom search spaces do not change this leakage boundary.

## Protected-group audit outputs

Each `ModelResult.protected_calibration` is a mapping from protected-column name
to a `calibration_table` built only from outer-test predictions for that model.
Each table keeps the raw subgroup label in `group`, retains missing labels as a
subgroup, and reports exposure, observed and predicted claim amount, pure
premiums, and O/P ratio. Multiple protected columns are audited independently,
not as intersections.

Provide review-ready categorical or pre-banded groups. Azoic does not infer bins
for continuous protected values. These tables are descriptive evidence for
review, not a fairness threshold, automated decision, or legal assessment.

## Complete YAML shape

Relative `data_path` values resolve from the YAML file's directory. If this
config is saved in `examples/`, `synthetic.parquet` means
`examples/synthetic.parquet`.

```yaml
name: motor-pricing-v1
data_path: synthetic.parquet

spec:
  target: claim_amount
  exposure: exposure
  claim_count: claim_count
  time_col: null
  protected_cols:
    - review_group

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
tuning: null

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
| `azoic profile` | `--data`, `--target`, `--exposure` | `--claim-count`, `--time-col`, `--out` | Screening table to stdout or CSV |
| `azoic fit` | `--config` | `--out`, `--quiet` | Markdown model card to stdout and/or a file |
| `azoic compare` | One or more config paths | `--out` | Comparison table to stdout or CSV |
| `azoic tune` | `--config` | `--trials` (YAML or 20), `--calibration-penalty` (YAML or 1.0), `--out`, `--quiet` | Best parameters plus Markdown model card |
| `azoic export-tariff` | `--config`, `--model`, `--out` | `--distill`, `--recalibrate/--no-recalibrate` | Three-sheet xlsx tariff |

Run `azoic COMMAND --help` for Typer's current option spellings.

## Workflow outputs

| Object | Contents |
|---|---|
| `Run` | Config, SHA-256 data fingerprint, row counts, exact train/test positions, feature names, and named `ModelResult` objects |
| `ModelResult` | Model kind, effective YAML parameters, diagnostic metrics, held-out calibration table, and `protected_calibration` mapping |
| Metrics | `gini_train`, `gini_test`, `op_ratio_test`, and exposure-weighted Tweedie `deviance_test` at fixed power 1.5 |
| Optional estimator mapping | Returned by `run_experiment(..., return_estimators=True)` |
| Model card | Markdown |
| Comparison | pandas table; `comparison_dashboard(runs)` optionally returns standalone Plotly HTML from Python |
| Tariff | `base_rate`, `factors`, and `mappings` workbook sheets |

`Run.train_indices` and `Run.test_indices` are immutable `tuple[int, ...]`
values containing the actual fit/evaluation row positions, in their original
partition order. All models within a run share those positions. For tuning,
`TuneResult.run` records the final **outer** partition, not an inner trial split.

Recover rows from the exact input frame without sorting, filtering, or changing
its index. The fingerprint covers shape, columns, dtypes, index, and values;
matching seeds or row counts alone cannot establish matching partitions. When
comparing runs, check both their fingerprints and their position tuples.

```python
train_frame = portfolio.iloc[list(run.train_indices)]
test_frame = portfolio.iloc[list(run.test_indices)]
```

Convert tuples to a list or integer array: pandas interprets a bare tuple as
row/column indexing. Use training positions for student fits and any
evaluation-phase recalibration base, and test positions for diagnostic and
distillation-fidelity frames. This scoping applies while candidates are being
evaluated; the production `export-tariff` default deliberately recalibrates on
the full loaded frame (see [Reporting and operations](../guide/operations.md)).
CLI `export-tariff --distill` uses the returned run's positions and rejects a
reloaded dataset whose fingerprint changed after fitting.

Run metrics describe raw estimator predictions. If applying a training-derived
scale factor later, label those adjusted diagnostics separately.

## Validation rules

- `ExperimentConfig`, `ModelSpec`, `PreprocessingSpec`, `TuningSpec`, and
  all parameter distributions reject extra fields.
- Data must be non-empty; exposure must be positive and finite; target and claim
  count must be non-negative and finite.
- Claim-count and target rows must be zero or positive together.
- Features must exist, be unique, and exclude special columns. Protected columns
  must be unique, non-empty, present in the data, and distinct from other special columns.
- Temporal splits reject absent or missing time values and keep timestamp ties
  together.
- Tweedie LightGBM power outside \([1.0, 2.0)\) fails.
- Frequency-severity requires both nested sub-specs and `spec.claim_count`.
- Tuning rejects unknown models, empty model spaces, unsupported or fixed
  parameters, invalid scalar distributions, and frequency-severity spaces.
- Preprocessing credibility by claims requires a claim-count column.
- Model prediction frames may omit outcome columns; fitted workflow pipelines
  supply harmless placeholders and drop them before the final estimator.

::: azoic.cli
