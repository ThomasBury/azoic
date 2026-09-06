# Reporting, comparison, tuning, MLflow, and tariff operations

Once candidates have a valid outer-test result, Azoic reuses the same `Run` for
human-readable reports, comparison, optional experiment tracking, and tariff
export.

## Write model cards and comparisons

```python
from pathlib import Path

from azoic.reporting import comparison_dashboard, comparison_table, model_card

Path("model-card.md").write_text(model_card(run), encoding="utf-8")

comparison = comparison_table([baseline_run, candidate_run])
comparison.to_csv("comparison.csv", index=False)
Path("comparison.html").write_text(
    comparison_dashboard([baseline_run, candidate_run]),
    encoding="utf-8",
)
```

A model card is Markdown and records the experiment data contract, fingerprint,
split, features, model parameters, held-out metrics, and a calibration preview.

The CLI can run several configs and write their comparison table:

```bash
azoic compare baseline.yaml candidate.yaml --out comparison.csv
```

The Python-only `comparison_dashboard` API returns standalone Plotly HTML and
requires the `plot` extra; the CSV table does not.

## Tune without touching outer test

```bash
uv add "azoic[tune]"
azoic tune --config experiment.yaml
```

Put optional trial settings and model-specific scalar distributions in the
experiment YAML:

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

A custom entry replaces that model's built-in search space; it is not merged
with the defaults. A model without a custom entry keeps the existing GLM or GBM
space exactly. `--trials` and `--calibration-penalty` override YAML values.
Omitted flags defer to YAML, then to the legacy defaults of 20 trials and 1.0.

`tune_experiment` still creates an inner split of outer training data,
minimizes Tweedie deviance plus a numeric O/P penalty, refits selected
parameters on all outer training data, and evaluates outer test once.
Configuration changes the candidate values, not this leakage boundary.

Invalid bounds, non-finite values, incompatible `step` and `log` settings,
empty spaces or categorical choices, unknown models or estimator parameters,
and extra fields fail while parsing the config. Family, link, objective,
Tweedie powers, exposure routing, and random seeds cannot be tuned.
Frequency-severity tuning remains unsupported.

!!! warning "Scale the calibration penalty"

    `abs(1 - O/P)` is unitless while Tweedie deviance depends on the portfolio.
    Increase the penalty only when calibration loss is too small to affect trial
    ordering; do not tune it on the final test result.

## Log a completed run to MLflow

```python
from azoic.mlops import log_run

run_id = log_run(
    run,
    tracking_uri="sqlite:///mlflow.db",
    experiment_name="motor-pricing",
    artifacts=["model-card.md", "comparison.csv"],
)
print(run_id)
```

Install `azoic[mlops]` first. `log_run` records the data fingerprint,
experiment fields, model parameters, finite metrics, and the requested files or
directories. Remote tracking remains an environment concern; Azoic does not
invent credentials or deployment policy.

## Export a multiplicative tariff

A fitted log-link `RiskGLM` or pipeline ending in one can be written to a
three-sheet workbook:

```bash
azoic export-tariff \
  --config experiment.yaml \
  --model tweedie-glm \
  --out tariff.xlsx
```

| Sheet | Contents |
|---|---|
| `base_rate` | Multiplicative base, family, resolved link, intercept, and recalibration metadata |
| `factors` | Numeric per-unit factors and categorical level relativities |
| `mappings` | Feature roles, levels, references, and fitted bin/group mappings |

Recalibration is on by default and shifts the base to reproduce observed
portfolio claim amount. Use `--no-recalibrate` only when the structural model
total is intentionally required.

A positive-objective GBM is not itself a multiplicative table. Distill a
held-out GLM student explicitly:

```bash
azoic export-tariff \
  --config experiment.yaml \
  --model tweedie-gbm \
  --distill \
  --out distilled-tariff.xlsx
```

The workbook describes the student and includes held-out teacher/student
fidelity metadata. Fidelity measures agreement with teacher predictions, not
accuracy against claims. The [freMTPL2 tutorial](fremtpl2.md) applies the workbook
after fitted preprocessing and compares it with the direct GLM, raw GBM, and
structured teacher on the same held-out claims. It exports with
`recalibrate=False` and training-frame feature metadata, then reports raw metrics
and a separate external multiplier based on each candidate's own training O/P,
including the applied workbook. Calibration, Lorenz, and common training-bin age
comparisons accompany deviance, D², Gini, O/P, and portfolio totals.

!!! danger "Application boundary"

    Tariff application rejects unseen categorical levels and non-finite numeric
    inputs. Do not silently map an unknown quote-time category into a factor.
    Resolve the data contract or publish an explicitly approved mapping first.

## Operational checklist

- Preserve the config, data fingerprint, and generated report together.
- Compare candidates on the same held-out rows.
- Record optional integrations without moving business logic into them.
- Check workbook totals and reference levels before deployment.
- Score an outcome-free frame to prove target and claim-count columns are not
  required at prediction time.
- Treat tariff deployment, approvals, monitoring, and rollback as downstream
  controls, not assumptions hidden inside a modelling library.

[Review configuration and CLI details](../reference/configuration-cli.md){ .md-button }
[Open the freMTPL2 operations example](fremtpl2.md){ .md-button .md-button--primary }
