# Experiment configuration and CLI

`ExperimentConfig` records the data contract, feature list, split,
preprocessing, and named candidates in one YAML file. The CLI is a thin shell
over the same Python workflow.

## Start from the checkout example

Generate the deterministic example data, then run both configured candidates:

```bash
uv run python -c "from tests.conftest import make_synthetic_portfolio as m; m(n=20000, seed=42).to_parquet('examples/synthetic.parquet')"
uv run azoic fit --config examples/tweedie.yaml
```

The YAML keeps model names stable and lets the workflow derive the exposure
column from `spec`:

```yaml
name: tweedie-v1
data_path: synthetic.parquet

spec:
  target: claim_amount
  exposure: exposure
  claim_count: claim_count

features:
  - driver_age
  - vehicle_age
  - region
  - vehicle_brand

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
  tweedie-gbm:
    kind: gbm
    params:
      objective: tweedie
      tweedie_variance_power: 1.5
      n_estimators: 50
      num_leaves: 15
      learning_rate: 0.05
      random_state: 42
```

!!! warning "Specials stay out of `features:`"

    Direct Python examples keep `exposure` inside `X`, where estimators read
    it as a sample weight. YAML `features:` must instead exclude every named
    special -- `target`, `exposure`, `claim_count`, `time_col`, and any
    `protected_cols` -- because the workflow derives them from `spec`.
    Listing one raises `ValueError` at config validation.

`protected_cols` names review-only columns that remain available for held-out
subgroup calibration but never enter preprocessing or model fitting. Declare it
only when the data carries such a column -- the checkout example has none.
Provide review-ready categorical or pre-banded groups; Azoic preserves their
labels and does not invent bins or pass/fail thresholds.

Relative `data_path` values resolve from the config file's directory, not the
process working directory, so a config and its data travel together. Here,
`synthetic.parquet` beside `examples/tweedie.yaml` resolves to
`examples/synthetic.parquet`.

## Run it from Python

```python
from azoic.workflow import ExperimentConfig, run_experiment

config = ExperimentConfig.from_yaml("examples/tweedie.yaml")
run, estimators = run_experiment(config, return_estimators=True)

for name, result in run.models.items():
    print(name, result.metrics)
```

A `Run` includes the validated config, data fingerprint, row counts, feature
names, and per-model metrics, overall calibration table, and protected-group
calibration tables when declared. Fitted estimators are returned only when
requested.

## Use task-oriented CLI commands

```bash
azoic profile --data portfolio.parquet --target claim_amount --exposure exposure
azoic fit --config experiment.yaml --out model-card.md
azoic compare baseline.yaml candidate.yaml --out comparison.csv
azoic tune --config experiment.yaml --trials 20 --out tuned-card.md
azoic export-tariff --config experiment.yaml --model tweedie-glm --out tariff.xlsx
```

!!! info "Extras stay task-specific"

    `tune` needs `azoic[tune]`. An HTML comparison dashboard needs
    `azoic[plot]`. MLflow is called from Python and needs `azoic[mlops]`.
    Plain fit, CSV comparison, model cards, and GLM tariff export use core.

The [configuration and CLI reference](../reference/configuration-cli.md)
documents every field, default, model parameter, nested frequency-severity
shape, command, output, and validation rule.

[Build diagnostics](diagnostics-visualization.md){ .md-button .md-button--primary }
[Open the complete schema](../reference/configuration-cli.md){ .md-button }
