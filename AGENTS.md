# AGENTS.md

> Quick rules for AI coding agents working on Azoic.
> For full product spec, scope, deferred items, and decisions see `PRD.md`.
> For milestone status see `PROGRESS.md`.

## Project overview

Azoic is a scikit-learn-compatible Python toolkit for non-life technical
tariff (pure premium) modelling: actuarial preprocessing, GLM (glum) + GBM
(LightGBM), frequency-severity, ranking/calibration diagnostics, reproducible
runs, multiplicative tariff xlsx export.

**Is**: pricing/pure-premium modelling. **Is NOT**: reserving, fraud, AutoML,
policy admin, Guidewire integration.

## Setup commands

- Install runtime only: `uv sync --no-dev`
- Install default development environment: `uv sync`
- Install everything: `uv sync --all-extras --all-groups`
- Install tutorial stack: `uv sync --group demo --extra mlops --extra plot`
- Run tests (fail fast): `uv run pytest -x`
- Run all tests: `uv run pytest`
- Lint: `uv run ruff check .`
- Type-check production code: `uv run ty check`
- Format: `uv run ruff format .`
- Combined check: `just check`
- Render freMTPL2 tutorial: `just demo` (external Quarto prerequisite)
- Build documentation: `just docs-build`
- CLI smoke: `uv run azoic --help` (after M5)

## Repo layout

```
src/azoic/
  data.py           # DatasetSpec, load_data
  profile.py        # profile_features, screen_features
  preprocessing.py  # AutoBinner, AutoGrouper
  models.py         # RiskGLM, RiskGBM, FrequencySeverityModel
  metrics.py        # gini, lorenz, calibration_table, one_way_table, double_lift_table; sklearn deviances re-exported
  validation.py     # make_strata, temporal_split
  plots.py          # plot_lorenz, plot_lift, plot_calibration, plot_one_way, plot_double_lift, plot_actual_vs_predicted (matplotlib)
  tariff.py         # distill_gbm; export_tariff(glm_or_pipeline, path)
  workflow.py       # ExperimentConfig, preprocessing/freq-sev YAML, run_experiment
  reporting.py      # model_card, comparison_table/dashboard
  mlops.py          # log_run (mlflow, lazy import)
  tune.py           # tune_experiment (optuna, lazy import) -- v0.2 part 1 / M7
  cli.py            # Typer entry point
tests/              # pytest; synthetic portfolio fixture in conftest.py
examples/fremtpl2.qmd # source-only executable freMTPL2 tutorial
```

13 flat modules. No `utils`. No subpackages. Don't create either without
checking `PRD.md` sections 3 and 9.

## Code style

- **sklearn API** — `fit`/`transform`/`predict`, fitted attrs end in `_`, no
  logic in `__init__`, params explicit **never** `**kwargs` (LightGBM kwargs
  break `get_params`).
- **No `utils.py` / dead scaffolding** — write code when it's used, not "for
  later".
- **pandas in/out at module boundaries; numpy inside**; add a Polars ingest extra
  only for a measured load-time or RAM bottleneck, and convert at the boundary.
- **New deps** go to a pyproject extra or dependency group (`demo`, `dev`, `docs`) with
  a one-line justification in the PR; never silently widen core.
- **Deliberate shortcuts** tagged `# ponytail: <known ceiling>, upgrade when
  <trigger>`.
- **No comments unless they encode a non-obvious rule** (e.g. the actuarial
  rules below) — code reads as intent.
- **Format**: ruff defaults, double quotes, line-length 100, py312 target.

## Actuarial rules (do not violate; full context in PRD.md sections 4-5)

1. Exposure is a **weight** for pure premium: `y = claim_amount/exposure`,
   `sample_weight=exposure`. Use `offset=log(exposure)` ONLY when
   `y = claim_amount` (aggregate). Never mix.
2. Frequency: `y = claim_count / exposure`, `sample_weight=exposure`, Poisson.
3. Severity: fit on `claim_count > 0` only (Gamma needs `y > 0`). The filter
   lives INSIDE `FrequencySeverityModel.fit`.
4. LightGBM `tweedie_variance_power`: `1.0 <= p < 2.0` — validate in
   `__init__`.
5. **Don't reimplement deviances** — `sklearn.metrics.mean_{tweedie,poisson,gamma}_deviance`
   accept `sample_weight`. Re-export/wrap only. `deviance_test` is exposure-
   weighted mean Tweedie deviance with fixed `power=1.5`.
6. Gini = concentration ranking only; aggregate tied prediction scores before
   integration. Never claim calibration from it; always pair with
   `calibration_table` + O/P ratio.
7. Primary diagnostics: `gini`, `lorenz`, `calibration_table`, O/P ratio,
   lift. RMSE/MAE/R^2/MAPE are secondary — warn when surfacing.
8. **Special columns travel inside X** (`exposure_col` etc.) — never as
   `fit(X, y, exposure=...)` kwargs; that breaks `GridSearchCV`.
9. Temporal splits reject missing times and keep equal timestamps on one side.
10. Tune on an inner split of outer training data; evaluate outer test once.
11. Tariff application rejects unseen categories and non-finite numerics.

## Testing

- `pytest`, seeded synthetic portfolio fixture in `tests/conftest.py`
  (`make_synthetic_portfolio(seed=42)`).
- Every estimator/transformer passes
  `sklearn.utils.estimator_checks.parametrize_with_checks`.
- No network, no S3, no real data in automated tests. Real-data fetching is
  permitted only during manual rendering of `examples/fremtpl2.qmd`.
- New module -> new `tests/test_<module>.py` with at least one runnable
  check.
- Keep tutorial HTML, Quarto caches/support files, fetched data, workbooks,
  reports, and MLflow state ignored; only the `.qmd` is source-controlled.
- Run `just check` (or `uv run ruff check . && uv run ty check && uv run pytest`) before
  finishing any task.

## PR / commits

- Commit prefixes: `feat:`, `fix:`, `chore:`, `docs:`, `test:`.
- ruff + pytest must be green before commit.
- If you change layout, commands, or conventions — update this file AND
  `PRD.md` / `PROGRESS.md` to match. Living docs.
- Don't commit secrets, large data, or notebooks' execution state
  (`.ipynb_checkpoints/` is gitignored).
