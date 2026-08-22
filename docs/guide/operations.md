# Reporting, comparison, tuning, MLflow, and tariff operations

Once candidates have a valid outer-test result, Azoic reuses the same `Run` for
human-readable reports, comparison, optional experiment tracking, and tariff
export.

## Write model cards and comparisons

```python
from pathlib import Path

from azoic.reporting import comparison_table, model_card

Path("model-card.md").write_text(model_card(run, fmt="md"), encoding="utf-8")
Path("model-card.html").write_text(model_card(run, fmt="html"), encoding="utf-8")

comparison = comparison_table([baseline_run, candidate_run])
comparison.to_csv("comparison.csv", index=False)
```

A model card records the experiment data contract, fingerprint, split, features,
model parameters, held-out metrics, and a calibration preview.

The CLI can run several configs and optionally write the Plotly dashboard:

```bash
azoic compare baseline.yaml candidate.yaml --out comparison.csv
azoic compare baseline.yaml candidate.yaml --out-html comparison.html
```

The HTML dashboard requires the `plot` extra; the CSV table does not.

## Tune without touching outer test

```bash
uv add "azoic[tune]"
azoic tune --config experiment.yaml --trials 20 --calibration-penalty 1.0
```

`tune_experiment` creates an inner split of outer training data, minimizes
Tweedie deviance plus a numeric O/P penalty, refits selected parameters on all
outer training data, and evaluates outer test once. Its built-in search space
covers GLM regularization and GBM tree structure. It does not tune nested
frequency-severity models.

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
fidelity metadata.

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
