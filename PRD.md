# Azoic — Product Requirements Document

> Single source of truth for scope, architecture, and conventions.
> For agent-facing quick rules see `AGENTS.md`. For status see `PROGRESS.md`.

## 1. What Azoic is

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
src/azoic/
  data.py          DatasetSpec (pydantic), load_data (pandas+pyarrow; s3 via fsspec)
  profile.py       profile_features() -> DataFrame; screen_features() -> keep/drop/review
  preprocessing.py AutoBinner, AutoGrouper (sklearn transformers; mapping_, set_mapping)
  models.py        RiskGLM, RiskGBM, FrequencySeverityModel
  metrics.py       gini, lorenz, calibration_table, one_way_table, double_lift_table; re-exports sklearn deviances
  validation.py    make_strata, temporal_split
  plots.py         plot_lorenz, plot_lift, plot_calibration, plot_one_way, plot_double_lift, plot_actual_vs_predicted (matplotlib)
  tariff.py        distill_gbm(); export_tariff(glm_or_pipeline, path) -> xlsx
  workflow.py      ExperimentConfig (preprocessing + freq-sev), run_experiment
  reporting.py     model_card, comparison_table
  mlops.py         log_run (thin mlflow; mlflow in [mlops] extra)
  tune.py          tune_experiment (optuna in [tune] extra)
  cli.py           Typer: profile / fit / compare / export-tariff / tune
```

13 flat modules. Stable interfaces (sklearn estimator protocol; calibration
table = DataFrame; run = frozen pydantic result) mean stopping after any
milestone never forces a refactor.

Documentation uses a task-first Zensical layout: `getting-started/` for
installation and the network-free first model, `guide/` for the conceptual
workflow plus five focused task guides and the freMTPL2 bridge, `reference/`
for comprehensive configuration/CLI and generated Python API pages, and
`javascripts/` only for the official MathJax integration. The Quarto tutorial
remains `examples/fremtpl2.qmd` and is linked rather than restyled.

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
2. **Frequency**: `y = claim_count / exposure`, `sample_weight=exposure`, Poisson.
3. **Severity**: fit on `claim_count > 0` only (Gamma requires `y > 0`). The
   filter lives INSIDE `FrequencySeverityModel.fit`, never in user code.
4. **LightGBM `tweedie_variance_power`**: `1.0 <= p < 2.0` (validate in
   `__init__`).
5. **Don't reimplement deviances** — `sklearn.metrics.mean_tweedie_deviance` /
   `mean_poisson_deviance` / `mean_gamma_deviance` all accept `sample_weight`.
   Re-export and wrap, never rewrite. The public `deviance_test` metric is
   exposure-weighted mean Tweedie deviance with fixed `power=1.5`.
6. **Concentration Gini measures ranking only** — policies are ordered from
   safest to riskiest (ascending `y_pred`); equal prediction scores are
   aggregated into single blocks before integration so the curve sits below
   the diagonal and the Gini is independent of row order. `gini = 1 - 2*auc`
   on the tie-corrected polygonal curve, numerically identical to the
   Frees-Meyers-Cummings midrank closed form. Never infer calibration from
   Gini; always pair it with `calibration_table` + O/P ratio. The Lorenz
   plot optionally overlays the perfect-model oracle curve and shades the
   Gini area.
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
  `screen_features`. Supervised grouping uses `sum(claim_amount) / sum(exposure)`;
  credibility floors use aggregate exposure and claim count. *Done when sklearn
  `parametrize_with_checks` passes;
  `mapping_` round-trips via `set_mapping`.*
- **M3 — models**: `RiskGLM`, `RiskGBM`, `FrequencySeverityModel`. *Done when
  fit/predict/score work with exposure_col; freq x sev approximates direct
  Tweedie within tolerance on synthetic data.*
- **M4 — validation + plots**: `make_strata`, `temporal_split`,
  lorenz/lift/calibration figures (matplotlib). Timestamp ties stay on one side
  of temporal holdouts. *Done when figures render headless to PNG.*
- **M5 — workflow + CLI**: YAML -> `ExperimentConfig`, `run_experiment()`,
  model card md/html, and CLI commands `profile`, `fit`, `compare`,
  `export-tariff`, and `tune`. *Done when an example
  config runs end-to-end on synthetic data.*
- **M6 — tariff + mlops**: `export_tariff` -> xlsx (base/factors/mappings
  sheets), `log_run` with mlflow. Tariff application rejects unknown categories
  and non-finite numerics. *Done when GLM export reproduces portfolio total;
  mlflow run shows params/metrics/artifacts.*
- **M7 — optuna tune objective (v0.2 part 1)**: `tune_experiment` runs one
  optuna study per named model with actuarial-aware objective
  (`deviance_test + calibration_penalty * |1 - op_ratio_test|` -- the numeric
  penalty that replaces the cut TariffOptimizer constraint DSL). Trials use an
  inner split of outer training data; best params are refit on outer training
  data and evaluated once on untouched outer test. `azoic tune` CLI.
  *Done when the tuned `Run` carries finite Gini / O-P ratio / deviance + a
  populated calibration table, and best params preserve YAML identity params
  (rules 1, 4 intact under search).*
- **M8 — executable freMTPL2 tutorial**: one source-controlled
  `examples/fremtpl2.qmd` demonstrates the complete technical-tariff workflow
  on pinned OpenML datasets 41214 and 41215: deterministic cleaning and
  sampling, profiling/screening, learned preprocessing, direct Tweedie GLM and
  GBM, Poisson/Gamma frequency-severity, held-out actuarial diagnostics,
  outcome-free scoring, tariff export, reporting, and local MLflow tracking.
  freMTPL2 is used instead of the narrower Swedish motorcycle data because one
  portfolio supports every workflow stage. Jupyter lives in the `demo`
  dependency group; the existing `mlops` and `plot` extras are reused, and
  Quarto remains an external prerequisite. Only the `.qmd` is source: fetched
  data, caches, HTML, workbooks, reports, and MLflow files stay under ignored
  `examples/_artifacts/fremtpl2/` or other ignored Quarto outputs. *Done when
  outcome-free pipeline predictions match labeled predictions, unit checks are
  green, and `just demo` renders one self-contained HTML tutorial from a clean
  generated-artifact state without making generated files visible to Git.*

- **v0.4 documentation onboarding**: task-first Zensical home, complete install
  and first-model path, five focused guides, comprehensive configuration/CLI
  reference, prominent freMTPL2 bridge, and MathJax 3 using Zensical's official
  helper. The default theme and existing dependencies remain unchanged.
  *Done when the documented first model and checkout YAML run,
  `just docs-build` is strict-green, generated HTML contains navigation, tables,
  highlighted code, Arithmatex wrappers, and both MathJax scripts, and project
  checks remain green.*

## 7. Later iterations (optional, none blocking)

- **v0.2** — optuna objective (`deviance + calibration penalty`) **(M7 -- done)**,
  monotonic binning + LGBM monotone_constraints **done**.
  OOT is an opt-in use of `temporal_split` when the dataset has any sortable period
  column; equal periods remain on one side and missing periods are rejected. Without
  an ordered period, only non-temporal validation is possible.
- **Conditional, no version** — add interactive diagnostic charts only when
  users have a real business need to explore individual charts; add a Polars
  ingest extra only when a real portfolio demonstrates an unacceptable pandas
  load-time or RAM bottleneck; keep pandas at Azoic's module boundaries.
- **v0.3** — GBM->tariff distillation **done**: positive-objective teachers use
  the existing experiment holdout for fidelity metrics and export a log-link GLM
  student through the unchanged three-sheet workbook contract.
- **Conditional, no version** — adjacency-aware geo grouping waits for a portfolio
  with real adjacency; remote MLflow waits for an endpoint; SHAP waits for
  interventional explanations or SHAP plots; SageMaker waits for a named target
  environment. LightGBM native
  contributions cover basic explanations without another dependency.

## 8. Dependencies

**Core (installed by `uv sync`):** numpy, pandas, scikit-learn, glum,
lightgbm, pyarrow, pydantic, pyyaml, typer, matplotlib, openpyxl.

**Extras:**
- `aws` — s3fs
- `mlops` — mlflow
- `tune` — optuna
- `demo` (dependency-group) — jupyter kernel for the executable tutorial
- `dev` (dependency-group) — pytest, ruff, pre-commit
- `docs` (dependency-group) — Zensical + mkdocstrings-python, documentation build only

`uv sync --no-dev` for runtime only; `uv sync` for the default development
environment; `uv sync --all-extras --all-groups` for everything.

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
| 5 clusterer classes | clustering = grouping | `AutoGrouper(strategy=...)`; geo adjacency only for a real constrained portfolio |
| 5 mlflow classes | thin shim is enough | `log_run()` function |
| `TariffOptimizer` constraint DSL strings | parser project | numeric penalties in optuna objective (v0.2) |
| 5 tariff exporter classes | one xlsx is the format | `export_tariff(glm, path)` |
| `TariffExperiment` sequencing class | functions compose | `run_experiment(config)` |
| `selection/` module (5 classes) | flags = profiler columns | `screen_features(profile)` |
| Hydra | one config, no composition yet | YAML + pydantic + Typer overrides |
| polars + duckdb in core | pandas is canonical | add Polars only for a measured ingest bottleneck; duckdb = notebook habit |
<<<<<<< HEAD
| plotly dual diagnostic backend | doubles test surface | matplotlib diagnostics only; add interactive charts only for a real business need |
| Textual, PowerPoint, ALE, geopandas | YAGNI for v1 | cut until concrete demand; M8 remains one `.qmd`, with Zensical publishing it, with Zensical publishing it |
=======
| plotly dual diagnostic backend | doubles test surface | existing Plotly comparison dashboard; add diagnostic charts only for a real business need |
| Textual, PowerPoint, ALE, geopandas | YAGNI for v1 | cut until concrete demand; M8 remains one `.qmd` linked from Zensical |
>>>>>>> 69f8553 (docs: add task-first onboarding guides)
| `pydantic AND dataclasses` | overlap | pydantic only |
| `ModelCard.to_pdf` | windows weasyprint pain | md + html only |

## 10. Decisions log

| Decision | Rationale |
|---|---|
| Python 3.12 (not 3.14) | glum/lightgbm wheels confirmed for 3.12; 3.14 too new |
| Preprocessing built fresh (not ported from arfs) | no arfs source located in `~/projects` |
| Defer Hydra | one config, no composition pain yet; Typer flags suffice |
<<<<<<< HEAD
| matplotlib diagnostics by default | headless PNG/PDF free; Plotly deferred until interactive charts have a business need |
| Zensical site | task-first navigation and generated tutorial HTML; no custom theme or JavaScript |
=======
| matplotlib diagnostics by default | headless PNG/PDF free; Plotly remains limited to the comparison dashboard until interactive charts have a business need |
| Zensical site | task-first navigation and generated tutorial HTML; default theme; JavaScript limited to Zensical's official MathJax helper and CDN runtime |
>>>>>>> 69f8553 (docs: add task-first onboarding guides)
| glum + lightgbm in core (not extras) | GLM/GBM is the package's point; avoid ImportError-on-import wart |
| mlflow in `mlops` extra (not core) | heavy; only needed at M6; `log_run` imports lazily |
| No additional OOT workflow helpers | `time_col` is optional and already accepts any sortable period (including year-month); a dataset without an ordered period cannot support OOT validation |
| Commit `uv.lock` + `.python-version` | reproducibility principle |
| freMTPL2 rather than Swedish motorcycle for M8 | one portfolio covers direct Tweedie, frequency-severity, preprocessing, evaluation, and tariff export |
| Commit only the M8 `.qmd` source | executable prose is durable; data, caches, and rendered outputs are reproducible artifacts |
