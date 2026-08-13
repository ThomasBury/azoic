# RiskForge — Progress

> Living tracker. Mirrors `PRD.md` section 6 milestones. Update after every
> chunk of work.

Legend: ☐ pending · ◐ in progress · ☑ done

## Milestones

- ☑ **M0 — scaffold** — uv, src layout, ruff, pytest, pre-commit,
  AGENTS/PRD/PROGRESS, smoke green.
- ☑ **M1 — data + metrics** — `DatasetSpec`, `load_data`, `gini`, `lorenz`,
  `calibration_table`, `op_ratio`, deviance re-exports.
- ☑ **M2 — preprocessing** — `AutoBinner`, `AutoGrouper`,
  `profile_features`, `screen_features`.
- ☑ **M3 — models** — `RiskGLM`, `RiskGBM`, `FrequencySeverityModel`.
- ☑ **M4 — validation + plots** — `make_strata`, `temporal_split`,
  lorenz/lift/calibration.
- ☑ **M5 — workflow + CLI** — `ExperimentConfig`, `run_experiment`,
  model card, Typer commands.
- ☑ **M6 — tariff + mlops** — `export_tariff` -> xlsx, `log_run`.
- ☑ **M7 — optuna tune (v0.2 part 1)** — `tune_experiment`, per-model optuna
  study, actuarial-aware numeric-penalty objective (`deviance_test +
  calibration_penalty * |1 - op_ratio_test|`), `riskforge tune` CLI.

## Current focus

v0.2 part 2 in progress: monotonic binning + LightGBM `monotone_constraints`
shipped (actuarial monotonic-relativity guarantee end-to-end -- bin means and
GBM splits cannot contradict each other). Next: plotly backend, comparison
dashboard, polars ingest extra (per `PRD.md` section 7). OOT uses the existing
optional temporal split only when the data has a sortable period column.
