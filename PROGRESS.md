# Azoic — Progress

> Living tracker. Mirrors `PRD.md` section 6 milestones. Update after every
> chunk of work.

Legend: ☐ pending · ◐ in progress · ☑ done

## Milestones

- ☑ **M0 — scaffold** — uv, src layout, ruff, pytest, pre-commit,
  AGENTS/PRD/PROGRESS, smoke green.
- ☑ **M1 — data + metrics** — `DatasetSpec`, `load_data`, `gini`, `lorenz`,
  `calibration_table`, `op_ratio`, tied-block concentration Gini, fixed-power
  exposure-weighted Tweedie deviance.
- ☑ **M2 — preprocessing** — `AutoBinner`, `AutoGrouper`, aggregate-claim
  relativities and credibility floors, `profile_features`, `screen_features`.
- ☑ **M3 — models** — `RiskGLM`, `RiskGBM`, `FrequencySeverityModel`.
- ☑ **M4 — validation + plots** — `make_strata`, tie-safe `temporal_split`,
  lorenz/lift/calibration, one-way/double-lift tables and chart renderers.
- ☑ **M5 — workflow + CLI** — `ExperimentConfig`, `run_experiment`,
  model card, Typer commands.
- ☑ **M6 — tariff + mlops** — strict `export_tariff` application -> xlsx,
  `log_run`.
- ☑ **M7 — optuna tune (v0.2 part 1)** — `tune_experiment`, per-model optuna
  inner-split study, outer-holdout evaluation, actuarial-aware numeric-penalty
  objective (`deviance_test + calibration_penalty * |1 - op_ratio_test|`),
  `azoic tune` CLI.
- ☑ **v0.2 part 2** — canonical dataset fingerprints; exposure-weighted
  calibration bins; distinct numeric missing bins; YAML preprocessing and
  frequency-severity pipelines; pipeline-aware tariff export; standalone
  comparison dashboard; one-million-row bin merge reduced from 3.12s to 0.066s.
- ☑ **M8 — executable freMTPL2 tutorial**
  - [x] unlabeled scoring fixed
  - [x] tutorial and demo dependency added
  - [x] reporting/MLflow/tariff artifacts demonstrated
  - [x] unit checks green
  - [x] clean-environment Quarto render verified
  - [x] living documentation finalized
- ☑ **v0.3 — exportable GBM distillation** — positive Tweedie/Poisson/Gamma
  GBMs distil to log-link GLM students on the existing train/test boundary;
  held-out fidelity and provenance travel in the three-sheet tariff workbook.
- ☑ **v0.4 — Azoic release** — renamed distribution, imports, and CLI; Zensical site and GitHub Pages/PyPI OIDC workflows.

## Current focus

v0.3 GBM-to-tariff distillation is implemented. Adjacency-aware grouping, remote
MLflow guidance, SHAP, and SageMaker remain demand-gated. Azoic 0.4.0 adds the renamed package, documentation site, and release workflows. Generated
tutorial files and artifacts stay ignored.
