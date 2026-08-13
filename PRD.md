# RiskForge — Product Requirements Document

> Single source of truth for scope, architecture, and conventions.
> For agent-facing quick rules see `AGENTS.md`. For status see `PROGRESS.md`.

## 1. What RiskForge is

A **scikit-learn-compatible** Python toolkit for **non-life technical tariff
(pure premium) modelling**, combining:

- actuarial preprocessing (auto-binning, auto-grouping, feature profiling),
- GLM (glum) and GBM (LightGBM) pure-premium models with frequency x severity
  decomposition,
- actuarial diagnostics ranking first (Gini, lift, calibration, O/P ratio),
- reproducible runs (config + mlflow),
- operational tariff export to a multiplicative table (xlsx).

### Is
technical tariff modelling · actuarial model comparison framework · GLM+GBM
workflow package · reproducible experimentation layer · reporting & tariff
export utility.

### Is NOT
policy admin system · reserving package · claims fraud platform · generic
AutoML · replacement for actuarial judgement · cloud data platform · Guidewire
integration engine.

## 2. Design principles

1. **scikit-learn API** — `fit`/`transform`/`predict`; fitted attrs end in `_`;
   params explicit (no `**kwargs` — LightGBM kwargs break sklearn compat);
   works with `Pipeline`/`ColumnTransformer`/`GridSearchCV`; passes
   `check_estimator`.
2. **Actuarial-first** — ranking, calibration, portfolio adequacy, relativity
   stability, O/P ratio are primary; RMSE/MAE/R^2 available but secondary and
   warned.
3. **Transparent** — every grouping/binning emits a `mapping_` you can inspect,
   override (`set_mapping`), and export; no silent collapse; actuary in the loop.
4. **Reproducible** — config (YAML + pydantic), `uv.lock`, canonical-frame
   fingerprint (shape, columns, dtypes, index, values), `log_run()` mlflow helper.

## 3. Module architecture (flat, no subpackages, no utils)

```
src/riskforge/
  data.py          DatasetSpec (pydantic), load_data (pandas+pyarrow; s3 via fsspec)
  profile.py       profile_features() -> DataFrame; screen_features() -> keep/drop/review
  preprocessing.py AutoBinner, AutoGrouper (sklearn transformers; mapping_, set_mapping)
  models.py        RiskGLM, RiskGBM, FrequencySeverityModel
  metrics.py       gini, lorenz, calibration_table; re-exports sklearn deviances
  validation.py    make_strata, temporal_split
  plots.py         plot_lorenz, plot_lift, plot_calibration (matplotlib)
  tariff.py        export_tariff(glm_or_pipeline, path) -> xlsx
  workflow.py      ExperimentConfig (preprocessing + freq-sev), run_experiment
  reporting.py     model_card, comparison_table, comparison_dashboard
  mlops.py         log_run (thin mlflow; mlflow in [mlops] extra)
  tune.py          tune_experiment (optuna in [tune] extra)
  cli.py           Typer: profile / fit / compare / export-tariff
```

13 flat modules. Stable interfaces (sklearn estimator protocol; calibration
table = DataFrame; run = dict of metrics + artifacts) mean stopping after any
milestone never forces a refactor.

## 4. Model API conventions

### Special columns travel inside X (not as fit kwargs)
sklearn's `GridSearchCV`/`cross_val_score` will not forward
`fit(X, y, exposure=...)`. So:
- Estimators take `exposure_col: str` and pop that column from X inside
  `fit`/`predict`.
- `FrequencySeverityModel` takes `exposure_col`, `claim_count_col`,
  `claim_amount_col`.

This keeps full sklearn compatibility (pipelines, grid search, CV).

### Backend wrappers expose explicit params (no `**kwargs`)
LightGBM `**kwargs` break `get_params`/sklearn (per LightGBM docs). `RiskGBM`
declares each used param explicitly.

## 5. Actuarial correctness rules (do not violate)

1. **Exposure is a weight, not an offset** when modelling pure premium.
   Pure premium GLM: `y = claim_amount / exposure`, `sample_weight=exposure`.
   Use log-link with `offset=log(exposure)` ONLY when `y = claim_amount`
   (aggregate form). Never mix.
2. **Frequency**: `y = claim_count`, `sample_weight=exposure`, Poisson deviance.
3. **Severity**: fit on `claim_count > 0` only (Gamma requires `y > 0`). The
   filter lives INSIDE `FrequencySeverityModel.fit`, never in user code.
4. **LightGBM `tweedie_variance_power`**: `1.0 <= p < 2.0` (validate in
   `__init__`).
5. **Don't reimplement deviances** — `sklearn.metrics.mean_tweedie_deviance` /
   `mean_poisson_deviance` / `mean_gamma_deviance` all accept `sample_weight`.
   Re-export and wrap, never rewrite.
6. **Gini measures ranking only** — never infer calibration from it. Always
   pair Gini with `calibration_table` + O/P ratio.
7. **Primary diagnostics**: `gini`, `lorenz`, `calibration_table`, O/P ratio,
   lift by decile. `RMSE`/`MAE`/`R^2`/`MAPE` are secondary and accompanied by a
   warning when surfaced.

## 6. Milestones

Each is independently shippable. Done-when = acceptance check.

- **M0 — scaffold**: uv project, src layout, ruff, pytest, pre-commit,
  AGENTS/PRD/PROGRESS, first green smoke test. *Done when `uv run pytest` and
  `uv run ruff check .` are green on the scaffold suite.*
- **M1 — data + metrics**: `DatasetSpec`, `load_data`, `gini`, `lorenz`,
  `calibration_table`, sklearn deviance re-exports. *Done when tests pass on a
  seeded synthetic portfolio.*
- **M2 — preprocessing**: `AutoBinner` (tree/quantile, min_exposure/min_claims),
  `AutoGrouper` (rare-level + similarity), `profile_features`,
  `screen_features`. *Done when sklearn `parametrize_with_checks` passes;
  `mapping_` round-trips via `set_mapping`.*
- **M3 — models**: `RiskGLM`, `RiskGBM`, `FrequencySeverityModel`. *Done when
  fit/predict/score work with exposure_col; freq x sev approximates direct
  Tweedie within tolerance on synthetic data.*
- **M4 — validation + plots**: `make_strata`, `temporal_split`,
  lorenz/lift/calibration figures (matplotlib). *Done when figures render
  headless to PNG.*
- **M5 — workflow + CLI**: YAML -> `ExperimentConfig`, `run_experiment()`,
  model card md/html, `riskforge profile/fit/compare`. *Done when an example
  config runs end-to-end on synthetic data.*
- **M6 — tariff + mlops**: `export_tariff` -> xlsx (base/factors/mappings
  sheets), `log_run` with mlflow. *Done when GLM export reproduces portfolio
  total; mlflow run shows params/metrics/artifacts.*
- **M7 — optuna tune objective (v0.2 part 1)**: `tune_experiment` runs one
  optuna study per named model with actuarial-aware objective
  (`deviance_test + calibration_penalty * |1 - op_ratio_test|` -- the numeric
  penalty that replaces the cut TariffOptimizer constraint DSL); per-model
  best params then drive a canonical `run_experiment`. `riskforge tune` CLI.
  *Done when the tuned `Run` carries finite Gini / O-P ratio / deviance + a
  populated calibration table, and best params preserve YAML identity params
  (rules 1, 4 intact under search).*

## 7. Later iterations (optional, none blocking)

- **v0.2** — optuna objective (`deviance + calibration penalty`) **(M7 -- done)**,
  monotonic binning + LGBM monotone_constraints and comparison dashboard **done**;
  plotly plot backend and polars ingest extra remain. OOT is an opt-in use of
  `temporal_split` when the dataset has any sortable period column; without one,
  only non-temporal validation is possible.
- **v0.3** — GBM->tariff distillation, adjacency-aware geo grouping,
  SageMaker/remote-mlflow examples, docs site (Zensical), shap extra, Textual
  TUI (only if demanded).

## 8. Dependencies

**Core (installed by `uv sync`):** numpy, pandas, scikit-learn, glum,
lightgbm, pyarrow, pydantic, pyyaml, typer, rich, matplotlib, openpyxl.

**Extras:**
- `aws` — s3fs
- `mlops` — mlflow
- `tune` — optuna
- `plot` — plotly (comparison dashboard only; lazy import)
- `dev` (dependency-group) — pytest, ruff, pre-commit

`uv sync --all-extras` for everything; `uv sync` for the core modelling stack.

## 9. Deferred / cut (do NOT reintroduce without checking PROGRESS.md)

These were in the original spec and intentionally dropped or merged. Re-adding
is over-engineering unless a concrete need appears.

| Cut/merged | Why | Replacement |
|---|---|---|
| 5 GLM estimator classes | class explosion | one `RiskGLM(family, link, exposure_col)` |
| 4 GBM estimator classes | class explosion | one `RiskGBM(objective, exposure_col)` |
| separate FreqSev wrappers per backend | needless duplication | one `FrequencySeverityModel(freq, sev)` (duck-typed) |
| `AutoTariffGLM` class | it's a Pipeline | construct `sklearn.pipeline.Pipeline` directly |
| 6 splitter classes | sklearn has it | `make_strata()` helper + sklearn splits; `temporal_split()` |
| custom deviance module | stdlib has it | re-export `sklearn.metrics.mean_*_deviance` |
| 5 clusterer classes | clustering = grouping | `AutoGrouper(strategy=...)`; geo adjacency -> v0.3 |
| 5 mlflow classes | thin shim is enough | `log_run()` function |
| `TariffOptimizer` constraint DSL strings | parser project | numeric penalties in optuna objective (v0.2) |
| 5 tariff exporter classes | one xlsx is the format | `export_tariff(glm, path)` |
| `TariffExperiment` sequencing class | functions compose | `run_experiment(config)` |
| `selection/` module (5 classes) | flags = profiler columns | `screen_features(profile)` |
| Hydra | one config, no composition yet | YAML + pydantic + Typer overrides |
| polars + duckdb in core | pandas is canonical | polars in v0.2 ingest extra; duckdb = notebook habit |
| plotly dual backend v1 | doubles test surface | matplotlib only v1; plotly v0.2 |
| Textual, PowerPoint, ALE, geopandas, docs site | YAGNI for v1 | cut, or v0.3 if demanded |
| `pydantic AND dataclasses` | overlap | pydantic only |
| `ModelCard.to_pdf` | windows weasyprint pain | md + html only |

## 10. Decisions log

| Decision | Rationale |
|---|---|
| Python 3.12 (not 3.14) | glum/lightgbm wheels confirmed for 3.12; 3.14 too new |
| Preprocessing built fresh (not ported from arfs) | no arfs source located in `~/projects` |
| Defer Hydra | one config, no composition pain yet; Typer flags suffice |
| matplotlib only through v1 | headless PNG/PDF free; plotly v0.2 |
| Zensical docs site at v0.3 | internal tool; docs not on critical path |
| glum + lightgbm in core (not extras) | GLM/GBM is the package's point; avoid ImportError-on-import wart |
| mlflow in `mlops` extra (not core) | heavy; only needed at M6; `log_run` imports lazily |
| No additional OOT workflow helpers | `time_col` is optional and already accepts any sortable period (including year-month); a dataset without an ordered period cannot support OOT validation |
| Commit `uv.lock` + `.python-version` | reproducibility principle |