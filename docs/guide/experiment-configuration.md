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
data_path: examples/synthetic.parquet

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
```

Relative `data_path` values resolve from the process working directory. Run the
example from the repository root.

## Run it from Python

```python
from azoic.workflow import ExperimentConfig, run_experiment

config = ExperimentConfig.from_yaml("examples/tweedie.yaml")
run, estimators = run_experiment(config, return_estimators=True)

for name, result in run.models.items():
    print(name, result.metrics)
```

A `Run` includes the validated config, data fingerprint, row counts, feature
names, and per-model metrics and calibration table. Fitted estimators are
returned only when requested.

## Use task-oriented CLI commands

```bash
azoic profile --data portfolio.parquet --target claim_amount --exposure exposure
azoic fit --config experiment.yaml --out model-card.md --out-html model-card.html
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
