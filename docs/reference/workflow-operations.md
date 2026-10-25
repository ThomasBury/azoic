# Workflow and operations API

!!! note "Unreleased checkout documentation"

    This page describes the current source checkout; some APIs differ from the
    published 0.5.0 package. For a release-compatible journey, start with the
    [first model](../getting-started/first-model.md). See
    [installation](../getting-started/installation.md) for the version boundary.

These APIs turn validated configuration into reproducible runs, reports,
optional tracking, tuning results, and exportable tariffs. Read
[experiment configuration](../guide/experiment-configuration.md) for the run
path and [reporting and operations](../guide/operations.md) for task-oriented
examples.

| Module | Public API | Purpose |
|---|---|---|
| `azoic.workflow` | `ExperimentConfig`, `ModelSpec`, `PreprocessingSpec`, `TuningSpec`, `FloatDistribution`, `IntDistribution`, `CategoricalDistribution`, `Run`, `ModelResult`, `check_experiment`, `run_experiment`, `save_run`, `load_run`, `revise_run` | Validated configuration, runs, persistence and refreshed revision diagnostics |
| `azoic.tariff` | `export_tariff`, `distill_gbm`, `extract_tariff`, `apply_tariff`, `recalibrate_for_total`, `RevisedTariff`, `revise_tariff` | Multiplicative xlsx export, distillation, tariff application and audited factor revisions |
| `azoic.reporting` | `model_card`, `comparison_table`, `comparison_dashboard` | Markdown model cards, comparison tables, standalone HTML dashboard strings |
| `azoic.mlops` | `log_run` | MLflow run logging (lazy import) |
| `azoic.tune` | `tune_experiment`, `TuneResult` | Optuna tuning on inner splits of outer training data |

::: azoic.workflow

::: azoic.tariff

::: azoic.reporting

::: azoic.mlops

::: azoic.tune
