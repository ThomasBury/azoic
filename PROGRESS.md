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
- ☑ **v0.2 part 2** — canonical dataset fingerprints; exposure-weighted
  calibration bins; distinct numeric missing bins; YAML preprocessing and
  frequency-severity pipelines; pipeline-aware tariff export; standalone
  comparison dashboard; one-million-row bin merge reduced from 3.12s to 0.066s.

## Current focus

v0.2 part 2 is complete: monotonic binning and LightGBM constraints, workflow
preprocessing/frequency-severity, reproducibility and diagnostics fixes, static
comparison reporting, and the measured bin-merge optimization are shipped.
Next optional work: Plotly backend for the existing plot functions and polars
ingest extra (per `PRD.md` section 7). OOT uses the existing optional temporal
split only when the data has a sortable period column.
