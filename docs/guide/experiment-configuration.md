# Experiment configuration and CLI

`ExperimentConfig` records the data contract, feature list, split,
preprocessing, and named candidates in one YAML file. The CLI is a thin shell
over the same Python workflow.

## Start with the installed package

Run the [first model](../getting-started/first-model.md) to create
`portfolio.parquet`, then save this as `experiment.yaml` beside that file.
This first configuration and its Python/CLI commands work with **Azoic 0.5.0**;
no checkout or test fixture is needed. The two commands below each train fresh
candidates, so choose Python or CLI for a run.

```yaml
name: first-comparison
data_path: portfolio.parquet

spec:
  target: claim_amount
  exposure: exposure
  claim_count: claim_count
  time_col: period

features:
  - driver_age
  - vehicle_age
  - region

split: temporal
test_size: 0.2
random_state: 42

models:
  tweedie-glm:
    kind: glm
    params:
      family: tweedie
      link: log
      tweedie_power: 1.5
      random_state: 42
  tweedie-gbm:
    kind: gbm
    params:
      objective: tweedie
      tweedie_variance_power: 1.5
      n_estimators: 50
      num_leaves: 15
      learning_rate: 0.05
      random_state: 42
      n_jobs: 1
```

```bash
uv run azoic fit --config experiment.yaml --out model-card.md
```

The API and model card call the held-out split `test`; treat it as development
validation while choosing models. A separate untouched final test is still needed.

!!! warning "Specials stay out of `features:`"

    Direct Python examples keep `exposure` inside `X`, where estimators read
    it as a sample weight. YAML `features:` must instead exclude every named
    special -- `target`, `exposure`, `claim_count`, `time_col`, and any
    `protected_cols` -- because the workflow derives them from `spec`.
    Listing one raises `ValueError` at config validation.

`protected_cols` names review-only columns that remain available for held-out
subgroup calibration but never enter preprocessing or model fitting. Declare it
only when the data carries such a column -- the starter has none.
Provide review-ready categorical or pre-banded groups; Azoic preserves their
labels and does not invent bins or pass/fail thresholds.

Relative `data_path` values resolve from the config file's directory, not the
process working directory, so a config and its data travel together. Here,
`portfolio.parquet` resolves beside `experiment.yaml`.

## Run it from Python

```python
from azoic.workflow import ExperimentConfig, run_experiment

config = ExperimentConfig.from_yaml("experiment.yaml")
run, estimators = run_experiment(config, return_estimators=True)

for name, result in run.models.items():
    print(name, result.metrics)
```

## Additional checkout capabilities

The rest of this section describes the **unreleased checkout**, not the 0.5.0
installation. In particular, 0.5.0 lacks `df=`, per-model `preprocess: false`,
the portfolio separation/check APIs, and the full constructor/runtime provenance fields below.

Before a real modelling exercise, [freeze development/final-test membership](actuarial-workflow.md#freeze-portfolio-membership-before-experimenting).
Keep the opening release-compatible example above unchanged; the following
checkout-only YAML records that guide's development contract. Save it beside
`development.parquet` as `development.yaml` and run the read-only check first.

```yaml
name: development-candidates
data_path: development.parquet
spec:
  target: claim_amount
  exposure: exposure
  claim_count: claim_count
  time_col: period
  id_col: record_id
  excluded_cols: [partition]
  exposure_unit: year
  currency: EUR
  observation_period: synthetic periods 0–19
  claim_valuation_basis: synthetic simulated ultimate amounts
  adjustments: [no external caps or adjustments]
features: [driver_age, vehicle_age, region]
split: temporal
models:
  glm:
    kind: glm
    params: {family: tweedie, link: log}
```

```bash
uv run azoic check --config development.yaml
```

This reads and checks the development portfolio without fitting, repairing,
dropping rows or writing files. The same result is available through
`check_experiment(ExperimentConfig.from_yaml("development.yaml"))`. Existing
fit/tune functions consume only the portfolio supplied: they do not discover or
open the separate final-test file. Comparisons label their results as development
evidence; the public metric suffix `_test` remains for development validation.

A `Run` includes the validated config, data fingerprint, row counts, feature
names, runtime versions, effective tuning settings when tuned, and per-model
resolved constructor settings, metrics, overall calibration table, and protected-group
calibration tables when declared. See [provenance and its limits](operations.md).
Fitted estimators are returned only when requested.

For a notebook portfolio already held in memory, pass
`run_experiment(config, df=portfolio, return_estimators=True)`;
`tune_experiment(config, df=portfolio)` accepts the same input. No Parquet read
occurs. Keep `data_path` in the configuration as metadata; the fingerprint
identifies the frame actually used.

When an experiment declares `preprocessing`, each model uses it by default.
Set `preprocess: false` on the raw GBM to compare it with a binned/grouped GLM
on one split:

```yaml
models:
  binned-glm:
    kind: glm
    params: {family: tweedie, link: log, tweedie_power: 1.5}
  raw-gbm:
    kind: gbm
    preprocess: false
    params: {objective: tweedie, tweedie_variance_power: 1.5}
```

## Use task-oriented CLI commands

```bash
uv run azoic profile --data portfolio.parquet --target claim_amount --exposure exposure
uv run azoic fit --config experiment.yaml --out model-card.md
uv run azoic compare baseline.yaml candidate.yaml --out comparison.csv
uv run azoic tune --config experiment.yaml --trials 20 --out tuned-card.md
uv run azoic export-tariff --config experiment.yaml --model tweedie-glm --out tariff.xlsx
```

`fit`, `compare`, `tune` and `export-tariff` train from their configurations.
They do not reuse the objects from an earlier command. In particular, exporting
the original YAML after tuning uses its original settings. The starter's Python
export retains the actual fitted GLM instead.

!!! info "Extras stay task-specific"

    `tune` needs `azoic[tune]`. An HTML comparison dashboard needs
    `azoic[plot]`. MLflow is called from Python and needs `azoic[mlops]`.
    Plain fit, CSV comparison, model cards, and GLM tariff export use core.

The [configuration and CLI reference](../reference/configuration-cli.md)
documents every field, default, model parameter, nested frequency-severity
shape, command, output, and validation rule.

[Build diagnostics](diagnostics-visualization.md){ .md-button .md-button--primary }
[Open the complete schema](../reference/configuration-cli.md){ .md-button }
