# Workflow and operations API

These APIs turn validated configuration into reproducible runs, reports,
optional tracking, tuning results, and exportable tariffs. Read
[experiment configuration](../guide/experiment-configuration.md) for the run
path and [reporting and operations](../guide/operations.md) for task-oriented
examples.

| Module | Public API | Purpose |
|---|---|---|
| `azoic.workflow` | `ExperimentConfig`, `ModelSpec`, `PreprocessingSpec`, `TuningSpec`, `FloatDistribution`, `IntDistribution`, `CategoricalDistribution`, `Run`, `ModelResult`, `run_experiment` | Validated experiment configuration and reproducible runs |
| `azoic.tariff` | `export_tariff`, `distill_gbm`, `extract_tariff`, `apply_tariff`, `recalibrate_for_total` | Multiplicative xlsx tariff export, GBM-to-GLM distillation, and tariff application |
| `azoic.reporting` | `model_card`, `comparison_table`, `comparison_dashboard` | Markdown model cards, comparison tables, standalone HTML dashboard strings |
| `azoic.mlops` | `log_run` | MLflow run logging (lazy import) |
| `azoic.tune` | `tune_experiment`, `TuneResult` | Optuna tuning on inner splits of outer training data |

::: azoic.workflow

::: azoic.tariff

::: azoic.reporting

::: azoic.mlops

::: azoic.tune
