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
GBM splits cannot contradict each other). Next: plotly backend, OOT workflow
helpers, comparison dashboard, polars ingest extra (per `PRD.md` section 7).

## What's done

### v0.2 part 2a (monotonic binning + GBM monotone_constraints)
- `src/riskforge/preprocessing.py` --
  - `AutoBinner(monotonic=False)` (`False | True | "increasing" | "decreasing"`).
    After the strategy edges are computed, weighted bin means are smoothed with
    `sklearn.isotonic.isotonic_regression(sample_weight=bin_exposure)` and
    adjacent bins whose smoothed mean matches are merged; the surviving edges
    form a strictly monotonic binning. Applied before `min_exposure` small-bin
    merge so credibility floors still run on the monotonic edges. No-op without
    a target (so `monotonic=True` on the standard quantile-only fit path
    silently produces the standard edges). Direction is parsed once via
    `_mono_direction()` and validated at fit time (init accepts arbitrary
    values for `parametrize_with_checks`; garbage raises in `fit`).
- `src/riskforge/models.py` --
  - `RiskGBM(monotone_constraints=None)`. Accepts `dict[str, int]` (resolved
    against `X.columns` at fit time; unknown keys raise; exposure entry is
    dropped automatically because `exposure_col` is popped before LGBM sees
    the design) or `sequence[int]` in pre-pop order (also auto-drops the
    exposure index). Values must lie in `{-1, 0, 1}`. Dict shape validated in
    `__init__`; list shape and unknown-column errors raised in `fit`. `_make_
    backend` now takes `pre_pop_names` / `post_pop_names` and resolves the
    constraint list once. `None` is unchanged -- `monotone_constraints=None`
    produces predictions bit-identical to the pre-change `RiskGBM`.
- New tests: 5 in `tests/test_preprocessing.py` (increasing bin means
  enforced; decreasing enforced; `False` default identical to no param; no
  target no-op; invalid direction raises) + 7 in `tests/test_models.py`
  (dict form, list form with exposure drop, `None` parity, invalid dict value
  in init, unknown dict column at fit, invalid list values at fit, dict
  requires DataFrame). `parametrize_with_checks` green for both.
- `just check` green: **370 passed, 4 skipped** (SCIPY_ARRAY_API) -- up from
  358 at the end of M7.

### M7 (optuna tune -- v0.2 part 1)
- `src/riskforge/tune.py` --
  - `tune_experiment(config, *, n_trials=20, calibration_penalty=1.0,
    direction="minimize", sampler=None, pruner=None, study_name=None,
    random_state=42, return_estimators=False) -> TuneResult | (TuneResult,
    dict[str, estimator])`. Lazy `import optuna`; raises `MissingTuneExtra`
    ("requires the `tune` extra (`uv sync --extra tune`); optuna could not be
    imported.") when the extra is absent -- the same shape as
    `riskforge.mlops.log_run`'s `MissingMLOpsExtra`. Optuna INFO logs are
    silenced to WARNING inside `_import_optuna` so a tuned run does not flood
    the actuary's CLI / pytest output.
  - Per-trial objective is the actuarial-aware numeric penalty decided in
    PRD sec. 9 (the cut `TariffOptimizer` constraint DSL -> numeric penalties
    in optuna objective): `deviance_test + calibration_penalty *
    abs(1.0 - op_ratio_test)`. NaN `op_ratio_test` (pred_total == 0 -- a
    worthless trial) returns `float("inf")` because optuna 4.x rejects NaN
    trial values; `inf` is allowed and ranks the trial as worst.
  - One study per named model (per-study fresh `TPESampler(seed=random_state
    + i)` so each model searches independently yet reproducibly; a
    caller-supplied sampler takes over and owns its own reseeding). The trial
    calls `run_experiment` with a single-model config carrying the sampled
    overrides -- no internal split-array duplication; `run_experiment` is
    deterministic on `config.random_state` so trial scores are
    apples-to-apples.
  - Default search space per kind (only regularization / tree-structure
    hyperparams are sampled; identity params stay on the YAML so PRD rules 1
    and 4 are never violated by a suggestion):
    - GLM: `alpha` log-uniform `[1e-6, 1.0]`, `l1_ratio` uniform `[0, 1]`.
    - GBM: `num_leaves` int `[4, 64]`, `learning_rate` log-uniform
      `[1e-3, 0.3]`, `n_estimators` int `[20, 300]`, `min_child_samples` int
      `[1, 100]`, `reg_alpha` / `reg_lambda` log-uniform `[1e-8, 10]`.
  - After the studies, one fresh `run_experiment(config-with-best-params)` -> a
    canonical `Run` driving `model_card` / `export_tariff` / `log_run`
    unchanged. `return_estimators=True` mirrors the same kwarg on
    `run_experiment` and returns `{name: fitted_estimator}` (the hook M6
    `export_tariff` uses against the tuned GLM).
  - `TuneResult` (frozen pydantic): `best_params: dict[str, dict[str, Any]]`
    (only the *sampled* hyperparams; identity params live on
    `Run.models[name].params`), `best_values: dict[str, float]`, `n_trials`,
    `run: Run`.
  - Ponytail ceiling: one default search space per `kind`. Add a
    config-driven `search_space` when a real portfolio needs model-specific
    ranges or extra params (`subsample` / `colsample_bytree` / LightGBM
    `monotone_constraints` -- the latter pairs with the v0.2 monotonic
    binning work).
- `src/riskforge/cli.py` -- new `riskforge tune --config C.yaml [--trials N]
  [--calibration-penalty P] [--out MD --out-html HTML] [-q]` command. Calls
  `tune_experiment` on the loaded config and writes the model card of the
  best fit (mirrors `fit`'s IO); prints one `tuned <name>: k=v, ...` summary
  line per model before the card echo so the actuary sees the chosen
  hyperparams at a glance. The optuna import stays lazy inside the command
  body so `riskforge --help` always lists `tune` (and so `fit` /
  `export-tariff` keep working without the `tune` extra installed -- see
  `test_cli_help_lists_five_commands`).
- New tests: `tests/test_tune.py` (12) + 3 CLI tune tests in
  `tests/test_cli.py`. M7 acceptance: `test_m7_acceptance_tuned_run_apples_to_apples`
  -- `TuneResult` carries every model's `best_params`, and the final `Run` is
  structurally equal to a direct `run_experiment(cfg)` (same `n_rows` /
  `n_train` / `n_test` / `feature_names` / `models` keys) and every tuned
  model has finite `gini_test` / `op_ratio_test` / `deviance_test` plus a
  populated calibration table.
- `tests/test_tune.py` / `tests/test_cli.py` use per-test
  `pytest.importorskip("optuna")` (NOT module-level) so the 4 skipped cases
  when the `tune` extra is absent are confined to the tune tests; the rest of
  `test_cli.py` keeps running under a core-only install.
- Reproducibility test asserts `best_params == best_params` (TPESampler is
  deterministic) plus `best_values` within `rel=1e-9` -- optuna's choices are
  identical, but the Tweedie deviance carries ULP-level BLAS noise across
  glum/LightGBM runs (worst case observed: 3.66M +- 9e-7, ~3e-14 relative);
  strict equality flaked here, the rel-tol assertion encodes the real
  reproducibility ceiling.
- `just check` green: **358 passed, 4 skipped** (SCIPY_ARRAY_API, not
  applicable) -- up from 343 passed at the end of M6.

### M6 (tariff + mlops)
- `src/riskforge/tariff.py` --
  - `export_tariff(glm, path, *, X, y, exposure_col, reference=None,
    recalibrate=True, mappings=None) -> Path` writes a 3-sheet xlsx
    (`base_rate` / `factors` / `mappings`) decomposing a fitted `RiskGLM`
    into a multiplicative tariff (PRD sec. 3). Only valid for a log-link
    GLM; the check runs on `backend.link_instance.__class__.__name__` (glum
    keeps `backend.link == "auto"` post-fit, so the resolved link class is
    the source of truth).
  - `extract_tariff(glm, *, reference=None) -> dict` exposes the structural
    decomposition: `base_rate` (intercept folded with reference-level
    coefficients), `reference` (one level per categorical, default =
    first-sorted, override via `reference=`), `numeric` (raw coef per
    numeric feature), `categorical` (`{feat: {level: factor relative to
    reference}}`, reference level = 1.0), `mapping` (`pd.DataFrame`
    self-documenting the encoding). Reference folding keeps
    `apply_tariff(extract_tariff(glm)) == glm.predict()` up to float
    round-off (test asserts `rtol=1e-6, atol=1e-3`).
  - `apply_tariff(tariff, X) -> ndarray` reconstructs per-row pure-premium
    rate from a tariff dict. Numeric features apply as
    `factor ** value`; categorical features apply as the matching-level
    factor (reference = 1.0; an unseen level defaults to factor 1.0,
    mirroring glum's `cat_missing_method="fail"` failing at predict -- the
    actuary overrides via `reference=`).
  - `recalibrate_for_total(tariff, *, predicted_total, observed_total) ->
    float` shifts the structural base so the tariff reproduces an observed
    portfolio total; the new base exactly reproduces
    `sum(rate * exposure) == observed_total` (test asserts `rel=1e-7`).
  - Ponytail ceiling: the upstream binning/grouping mapping lives in
    `AutoBinner` / `AutoGrouper` of `preprocessing.py`; v1
    `workflow.run_experiment` feeds raw features to the GLM so the CLI
    ships no upstream mapping. The `mappings=` kwarg concatenates a
    caller-supplied `pd.DataFrame` or `dict[str, pd.DataFrame]` to the
    `mappings` sheet (AutoBinner / AutoGrouper emission) so the xlsx
    self-documents once a real pipeline wires one in.
- `src/riskforge/mlops.py` --
  - `log_run(run, *, tracking_uri=None, experiment_name=None, run_name=None,
    artifacts=None, artifact_path="artifacts") -> str` (mlflow `run_id`).
    Lazy `import mlflow`; raises `MissingMLOpsExtra` ("requires the `mlops`
    extra (`uv sync --extra mlops`); mlflow could not be imported.") when
    the extra is absent. Records `experiment.*` top-level params (config
    name, split, test_size, random_state, n_rows / n_train / n_test,
    `feature_names` CSV), per-model `<model>.kind` + `<model>.params.<k>`
    params, and `<model>.<metric>` metrics (NaN / inf metrics are silently
    skipped -- mlflow 3.x rejects them). Artifacts land under
    `artifact_path`; a directory is uploaded under
    `<artifact_path>/<dir_name>` so the directory name is preserved in the
    artifact tree (mlflow's `log_artifacts` uploads contents flat under
    `artifact_path` otherwise). One function -- no fluent API / custom
    classes -- the whole M6 mlops surface (PRD sec. 9 cut list).
- `src/riskforge/cli.py` -- new `riskforge export-tariff --config C.yaml
  --model NAME --out P.xlsx [--no-recalibrate]` command. Runs the config
  via `run_experiment(..., return_estimators=True)`, picks the named GLM,
  loads the data once, and writes the multiplicative-tariff xlsx.
  Rejects a non-GLM model name (e.g. `gbm-tweedie`) with a clear
  `BadParameter` message -- a tree model has no multiplicative tariff.
- New tests: `tests/test_tariff.py` (23), `tests/test_mlops.py` (9),
  `tests/test_cli.py` extended with 5 `export-tariff` cases (4 new + the
  `test_cli_help_lists_four_commands` parity check covering all four
  commands). M6 acceptance: `test_m6_acceptance_tariff_reproduces_portfolio_total`
  (recalibrated xlsx, re-applied via `apply_tariff`, reproduces
  `sum(claim_amount)` within `rel=1e-6`) and
  `test_m6_acceptance_mlflow_run_records_params_metrics_artifacts`
  (a logged run records experiment + per-model params, finite per-model
  metrics, and the model-card artifact).
- `tests/test_mlops.py` uses a per-test `sqlite:///<tmp>/mlflow.db`
  tracking URI -- mlflow 3.x puts the file store in maintenance mode
  (`set_tracking_uri("file://...")` raises); sqlite is the guided
  replacement and gives clean per-test isolation. Assertions read via
  `mlflow.get_run(rid).data` and `MlflowClient().list_artifacts(...)` --
  the fluent `mlflow.load_run` / `mlflow.list_artifacts` were removed in
  mlflow 3.x.
- M4 line duplicated in the milestone list -- collapsed to one entry; no
  content lost.
- `just check` green: **343 passed, 4 skipped** (SCIPY_ARRAY_API, not
  applicable) -- up from 306 passed at the end of M5.

### M5 (workflow + CLI)
- `src/riskforge/workflow.py` --
  - `ModelSpec(kind: "glm"|"gbm", params: dict)` builds an unfitted
    `RiskGLM` / `RiskGBM` from the kwargs. Ponytail ceiling:
    `FrequencySeverityModel` would need nested freq/sev sub-specs -- add
    a sub-spec path when a config wants it.
  - `ExperimentConfig` (pydantic, `extra="forbid"`): `name`, `data_path`,
    `spec: DatasetSpec`, `features: list[str] | None` (default = every column
    not in `spec.required_columns()`), `split: "random"|"temporal"`,
    `test_size`, `random_state`, `models: dict[str, ModelSpec]`.
    `ExperimentConfig.from_yaml(path)` round-trips YAML via `load_yaml`.
    `feature_columns(df)` resolves the feature list (explicit or implicit)
    and validates explicit features against `df.columns`.
  - `run_experiment(config, *, return_estimators=False) -> Run` (or `(Run,
    dict[str, estimator])` when `return_estimators=True`; the dict lets the
    M6 `export_tariff` reach a fitted GLM without re-fitting). Loads data via
    `load_data(spec=...)`, resolves features, splits (`np.random.permutation`
    shuffle or `temporal_split(spec.time_col, test_size)` -- the temporal
    split requires `spec.time_col`, raises a clear `ValueError` otherwise),
    fits every named model on `y = claim_amount / exposure` with
    `exposure_col` weight routing (PRD rule 1), and emits a `ModelResult`
    per model with `gini_train`, `gini_test`, `op_ratio_test`,
    `deviance_test` (Tweedie p=1.5 by default; Poisson deviance only when
    the model is a Poisson *frequency* fit) + a 10-decile `calibration_table`
    on the test set (observed = aggregate claim_amount, predicted = rate,
    weight = exposure -- the metrics.py convention).
  - `Run` (frozen pydantic) is the artifact: `config`, `n_rows`, `n_train`,
    `n_test`, `feature_names`, `models: dict[str, ModelResult]`. `Run[name]`
    shortcuts to `Run.models[name]`.
- `src/riskforge/reporting.py` --
  - `model_card(run, *, fmt="md"|"html") -> str`. Markdown is canonical: a
    header (config name, data path, split, target/exposure, row counts,
    feature list) + a per-model block (params, gini train/test, O/P ratio,
    deviance, a 12-row calibration-table preview as a markdown table).
    Ponytail ceiling: `fmt="html"` wraps the markdown in a minimal HTML5
    `<pre>` body (escaped) -- replace with a real markdown parser in a
    `reporting` extra when reports need styling.
  - `write_model_card(run, path, *, fmt)` writes the card text and returns
    the path.
- `src/riskforge/cli.py` -- Typer app `riskforge` (no_args_is_help,
  add_completion=False). Fresh `Console()` per call so
  `typer.testing.CliRunner` captures rich output (a module-level console
  captures the real stdout at import time and bypasses runner patching).
  Commands:
  - `riskforge profile --data P --target T --exposure E
    [--claim-count C --time-col T --id-col I] [--out OUT.csv]` -- runs
    `profile_features` + `screen_features`; `--out` writes the screening
    table to CSV, otherwise prints a rich table.
  - `riskforge fit --config C.yaml [--out MD --out-html HTML] [-q]` -- calls
    `ExperimentConfig.from_yaml` -> `run_experiment` -> `model_card`. Writes
    md / html to the requested paths; the markdown body is printed with
    `typer.echo` (rich markup off) so `[`/`]` in the card are not parsed.
  - `riskforge compare CFG1.yaml CFG2.yaml [...] [--out CSV]` -- runs each
    config and assembles a `config / model / kind / gini_train / gini_test /
    op_ratio_test / deviance_test` rowset; `--out` writes CSV, otherwise
    prints a rich `Table`.
- `examples/tweedie.yaml` -- example `ExperimentConfig` (direct Tweedie
  GLM + GBM on the synthetic portfolio). Comment header documents how to
  generate `data/synthetic.parquet` from `make_synthetic_portfolio`.
- New tests: `tests/test_workflow.py` (12), `tests/test_reporting.py` (9),
  `tests/test_cli.py` (8). M5 acceptance test
  (`test_m5_acceptance_example_config_runs_end_to_end`) writes a parquet,
  loads a config via `ExperimentConfig.from_yaml`, runs `run_experiment`,
  asserts both models fit / predict / score with `gini_test > 0` and
  `op_ratio_test` in `[0.5, 1.5]` and the calibration table populates.
  `just check` green: **306 passed, 4 skipped** (SCIPY_ARRAY_API, not
  applicable) -- up from 277 passed at the end of M4.
- Ruff config: `per-file-ignores` silences `B008` for `src/riskforge/cli.py`
  -- Typer's documented idiom uses `typer.Option(...)` as a parameter
  default; ruff's B008 misfires on it (same pattern as FastAPI / click).

### M4 (validation + plots)
- `src/riskforge/validation.py` --
  - `make_strata(y, sample_weight=None, *, n_strata=10) -> ndarray[int]`
    returns integer stratum codes for sklearn's `StratifiedKFold` /
    `StratifiedGroupKFold` on a continuous target (sklearn has no
    continuous-target stratifier built in). Exposure-weighted quantiles when
    `sample_weight` is given (each fold carries similar portfolio adequacy --
    the actuarial CV convention); unweighted `pd.qcut` otherwise. NaN rows
    map to `-1`. The function never splits itself; the splitter does.
  - `temporal_split(df, time_col, *, test_size=None, cutoff=None)
    -> (train_idx, test_idx)`. Single temporal holdout (the case
    `TimeSeriesSplit` does not cover directly). Rows are sorted by `time_col`
    ascending so train precedes test -- no leakage -- regardless of input
    order. Pass exactly one of `test_size` (float in `(0, 1)` -> round(n *
    test_size) latest rows, or int count) or `cutoff` (scalar comparable to
    `df[time_col]`; `<= cutoff` -> train, `> cutoff` -> test). Returns
    positional integer indices into the input `df`.
- `src/riskforge/plots.py` -- three thin matplotlib functions on top of
  `riskforge.metrics.lorenz` / `calibration_table`. Pass `ax=` to embed in
  your own figure, or `path=` to save a PNG (dpi=120, bbox_inches="tight").
  The module never forces a backend; tests / scripts set
  `matplotlib.use("Agg")` before importing for headless rendering (no
  display). PRD M4 done-when: figures render headless to PNG.
  - `plot_lorenz(y_true, y_pred, sample_weight=None, *, ax=None, path=None,
    title=...)` plots the model curve with the random reference diagonal and
    the gini in the legend label.
  - `plot_lift(table, *, baseline="observed", ax=None, path=None, title=...)`
    bar chart of `observed_pure_premium / portfolio_observed_pp` per segment
    with a `1.0` reference line. Ranking diagnostic; pairs with the
    calibration plot for level adequacy. `baseline` can be `"observed"`
    (default; uses ``claim_amount.sum() / exposure.sum()``) or a scalar > 0.
  - `plot_calibration(table, *, ax=None, path=None, title=...)` scatter of
    observed vs predicted pure premium per segment with the `y=x` line. Level
    adequacy diagnostic; ranking is read from the Lorenz plot, never this one.
- `tests/test_validation.py` (16 tests) and `tests/test_plots.py` (7 tests).
  `just check` green: **277 passed, 4 skipped** (SCIPY_ARRAY_API, not
  applicable) -- up from 254 passed at the end of M3.
- Decision recorded: `make_strata` returns integer codes only (never splits
  itself -- the splitter is sklearn's job). The unweighted path inherits
  pandas' `qcut(..., duplicates="drop", labels=False)` policy of keeping the
  original index of surviving bin edges, so the label set need not be
  contiguous `0..k-1` integers -- `StratifiedKFold` only needs distinct
  labels, so this is fine; documented in the docstring and the test.
- Bug caught during M4: the initial exposure-balance test used the synthetic
  portfolio's observed pure premium (`claim_amount / exposure`) as the
  stratification target, but ~80-90 % of synthetic policies have zero claims,
  so `pure_premium = 0` for most rows -- the dominant zero mass collapsed the
  strata and the +/-25 % balance assertion failed. Switched that test to a
  continuous uniform `y` so the weighted-edge algorithm is exercised in
  isolation; `make_strata` is documented to expect a non-degenerate continuous
  target.

### M3 (models + freq x severity)
- `src/riskforge/models.py` —
  - `RiskGLM(family, link, exposure_col, tweedie_power, alpha, l1_ratio, ...)`
    wraps `glum.GeneralizedLinearRegressor`. `exposure_col` popped from X and
    forwarded as `sample_weight` (pure-premium convention PRD rule 1). Default
    `alpha=0.001` so glum stays well-conditioned on wide designs
    (`alpha=0` is the unpenalized MLE). Re-exposes `backend_`, `coef_`,
    `intercept_`, `n_iter_` for tarification at M6. Aware of Poisson / Gamma /
    Tweedie `positive_only` and `poor_score` sklearn tags.
  - `RiskGBM(objective, exposure_col, tweedie_variance_power, ...)` wraps
    `lightgbm.LGBMRegressor`. Every used LightGBM param is declared explicitly
    (no `**kwargs` -- PRD rule 4 / AGENTS `get_params`). Tweedie power
    validated in `__init__` (guarded for non-scalar smoke values to satisfy
    `check_do_not_raise_errors_in_init_or_set_params`) and re-validated in
    `_make_backend` so a stray `set_params` still raises at fit time.
    Overrides `score` with family-aware D² via `sklearn.metrics.d2_tweedie_score`.
  - `FrequencySeverityModel(freq, sev, exposure_col, claim_count_col,
    claim_amount_col)` -- duck-typed meta-estimator. Pops all three special
    cols (rule 8), fits Poisson frequency
    (`y=claim_count/exposure`, `sample_weight=exposure`) and Gamma severity
    (`y=claim_amount/claim_count`, `sample_weight=claim_count`) on the
    `claim_count > 0` subset (rule 3 filter lives inside `fit`, never in user
    code). `predict(X) = freq.predict * sev.predict = pure premium per
    exposure unit`. Sub-estimators cloned via sklearn `clone`; user is
    expected to pass e.g. `RiskGLM` / `RiskGBM` / any estimator exposing
    `fit(X, y, sample_weight=...)` + `predict(X)`.
  - `make_tariff_pipeline(pre, estimator)` thin `sklearn.pipeline.Pipeline`
    factory, scaffolded for M5.
- Helpers: `_pop_weight` routes weight-column popping / `sample_weight`
  override for the FreqSev orchestrator. `_categorize_strings` casts object
  columns to `category` dtype so glum/LightGBM pick up their native categorical
  encoding. `_check_all_zero_weight` raises the sklearn-shaped error for
  all-zero `sample_weight`. `_store_fit_meta` / `_check_predict_meta` route
  ndarray inputs through `validate_data` so sparse / complex payloads raise
  the exact wording estimator checks expect (DataFrame inputs trusted as-is).
- `tests/test_models.py` -- `parametrize_with_checks([RiskGLM(), RiskGBM()])`
  green; functional tests for direct Poisson / Tweedie / Gamma fits,
  `exposure_col` weight routing, Tweedie-power validation both in `__init__`
  and after `set_params`; FreqSev basic fit/predict/score, severity-filter
  spy verifies the `claim_count > 0` subset, missing-subestimator guard, and
  the M3 acceptance test "freq x sev approximates direct Tweedie":
  in-sample `gini_fs > 0.05` and `|gini_fs - gini_tweedie| < 0.25`, plus
  `op_ratio` in `[0.85, 1.15]` for both, and `|op_fs - op_tweedie| < 0.10`.
  FrequencySeverityModel is intentionally NOT in `parametrize_with_checks`
  (meta-estimator with named special cols -- incompatible with the standard
  sklearn estimator contract exercised by those checks).
- `just check` green: **254 passed, 4 skipped** (SCIPY_ARRAY_API, not
  applicable).
- Bug caught during M3: passing the whole portfolio DataFrame (with
  `claim_count` / `claim_amount` columns still in X) to a *direct*
  `RiskGLM`/`RiskGBM` leaks the target; only `exposure_col` is auto-popped.
  Public estimators document this and tests pass a clean feature+exposure
  frame; `FrequencySeverityModel` strips all three special cols itself (rule 8).
- Bug caught during M3: with default `alpha=0.0`, glum's OLS on wide designs
  fails `check_sample_weight_equivalence_on_dense_data` (ill-conditioned
  Hessian); default got bumped to `alpha=0.001` and documented.

### M2 (preprocessing + profiling)
- `src/riskforge/preprocessing.py` — `AutoBinner` (quantile / tree strategies;
  exposure-weighted edges; `min_exposure` small-bin merge; `mapping_` +
  `set_mapping` round-trip; readable interval labels for DataFrame output, int
  bin codes for ndarray), `AutoGrouper` ("rare" floor-based and "similarity"
  greedy 1-D pure-premium merge; `max_groups`, `min_exposure`/`min_claims`;
  unknown levels → `other_label`). Both pass `parametrize_with_checks`.
- `src/riskforge/profile.py` — `profile_features` (cheap per-column screening
  stats) and `screen_features` (keep/bin/group/drop with reasons).
- `_check_input` gate rejects sparse/complex/1-D/0-feature/0-sample arrays and
  enforces n_features consistency on transform; sklearn-exact error wording so
  `match=...` checks pass. `input_tags.allow_nan` + `string` set.
- `tests/test_preprocessing.py` (functional + estimator checks) and
  `tests/test_profile.py`. `just check` green: 126 passed, 2 skipped
  (SCIPY_ARRAY_API, not applicable).

### M0 (scaffold)
- uv lib project at Python 3.12, src layout, `pyproject.toml` with core deps
  (numpy, pandas, scikit-learn, glum, lightgbm, pyarrow, pydantic, pyyaml,
  typer, rich, matplotlib, openpyxl) and extras (`aws`, `mlops`, `tune`,
  `plot`, `explain`); `dev` dependency-group.
- Ruff (lint + format) and pytest configured in `pyproject.toml`.
- `justfile` (test/lint/format/check/sync). `.pre-commit-config.yaml`
  (ruff + ruff-format, local-system hook).
- `AGENTS.md` (tight agent rules), `PRD.md` (full spec), this file.
- `tests/test_smoke.py` green — version + dependency imports.
- `uv.lock` committed (reproducibility). 18 tests green via `just check`.
- Network note: corporate TLS interception; use `$env:UV_SYSTEM_CERTS=1`
  for any `uv sync`/`uv run`.

### M1 (data + metrics)
- `src/riskforge/data.py` — `DatasetSpec` (pydantic, validated target/exposure)
  + `load_data` (parquet, local + s3 via fsspec, spec validation).
- `src/riskforge/metrics.py` — exposure-weighted `gini` (concentration index,
  actuarial convention: high-risk-first, `gini = 2*area - 1`), `lorenz` (returns
  `Lorenz` value record of curve arrays + gini), `calibration_table` (per
  segment observed/predicted PP + O/P ratio; deciles of predicted risk by
  default, `groups=` for arbitrary segments), `op_ratio`; sklearn
  `mean_{tweedie,poisson,gamma}_deviance` re-exported.
- `tests/conftest.py` — `make_synthetic_portfolio(n, seed)` deterministic
  actuarially-plausible portfolio (exposure, features, Poisson freq, gamma
  severity) + `synthetic_portfolio` session fixture.
- `tests/test_metrics.py` (11 tests) and `tests/test_data.py` (6 tests):
  18 tests green. `just check` (= ruff + pytest) green.
- Bug caught and fixed: initial Gini sign was inverted for the actuarial
  descending-sort convention.

## Next

v1 shippable end-to-end: data -> profile -> preprocessing -> models ->
validation/plots -> workflow/CLI -> tariff xlsx + mlflow. v0.2 part 1 (M7)
shipped: optuna objective (deviance + calibration penalty). v0.2 part 2a
shipped: monotonic binning + LightGBM `monotone_constraints`. Remaining v0.2
part 2 candidates (see `PRD.md` section 7): plotly backend, OOT workflow
helpers, comparison dashboard, polars ingest extra.

## Decisions log (most recent first)

| Decision | Rationale |
|---|---|
| `RiskGBM.monotone_constraints` accepts `dict[str, int]` or `sequence[int]`; both auto-drop the `exposure_col` index | `exposure_col` is popped before LGBM sees the design; without auto-drop the dict case would silently misalign and the list case would crash with a LightGBM feature-count check. Pre-pop dict keys / list indices match `X.columns` so the user writes constraints in their X-as-given order; the actuary doesn't have to remember that exposure is internally stripped |
| `AutoBinner.monotonic` runs after strategy edges but before `min_exposure` small-bin merge | monotonicity is the *actuarial* guarantee (PRD rule 6 territory); the credibility floor is an orthogonal operational requirement. Smoothing first keeps the floor honest: a monotonic-only bin still has to satisfy the per-bin exposure minimum after merging. Reversing the order would let `min_exposure` carve up the smoothed bins and re-introduce local non-monotonicity |
| Bin-mean smoothing via `sklearn.isotonic.isotonic_regression` (not a from-scratch pool-adjacent-violators) | sklearn already has the weighted PAVA; re-implementing it is the "5 clusterer classes" anti-pattern PRD sec. 9 cut. Sample-weight is `bin_exposure` so a bin holding 5 % of the portfolio doesn't drag a 60 % bin's mean around |
| `monotonic` validated at fit time, not `__init__` | matches the existing `tweedie_variance_power` pattern (guarded init + re-check in `_make_backend`); `parametrize_with_checks` feeds arbitrary smoke values to every parameter and an over-strict `__init__` breaks that contract |
| Monotonic binning + monotone_constraints exposed as two separate opt-in params | the actuary usually constrains one or the other independently; AutoBinner monotonic gives a stable relativity table (the tariff-friendly view); RiskGBM monotone_constraints gives a constrained learner that can be paired with non-monotonic binning. Forcing them to be configured together would over-couple two independent decisions |
| `RiskGBM(monotone_constraints=None)` is bit-identical to pre-change `RiskGBM` | the parametrize_with_checks set is unchanged; nothing breaks downstream (workflow / tune / tariff) and the test `test_riskgbm_monotone_constraints_none_default_unchanged` locks the parity in |
| `tune_experiment` calls `run_experiment` per trial (no internal split-array duplication) | `run_experiment` is deterministic on `config.random_state`; the same train/test split is reused across trials, so trial scores are apples-to-apples. The reload + split cost per trial is dwarfed by the fit cost, and centralising the array-prep keeps `tune.py` ~150 lines with zero copy-paste from `workflow.py` |
| Per-trial objective = `deviance_test + calibration_penalty * abs(1 - op_ratio_test)`; NaN op_ratio -> `inf` | PRD sec. 9 cut the TariffOptimizer constraint DSL and routed it to "numeric penalties in optuna objective (v0.2)"; op_ratio NaN (pred_total == 0) is a worthless trial, optuna 4.x rejects NaN -- `inf` is allowed and ranks the trial worst without a separate failure channel |
| One optuna study per named model (not one joint study across all models) | each model has its own search space; a joint trial would sample incompatible params across models and give one cross-model winner. Per-model studies give per-model optima the actuary wants; cross-model comparison stays at the `compare` / `model_card` workflow layer |
| Per-study fresh `TPESampler(seed=random_state + i)`; caller-supplied sampler wins | independent yet reproducible searches per model; a single shared seeded sampler with cross-study state would leak RNG progress between models and is fragile in optuna 4.x |
| Default search space touches only regularisation / tree-structure hyperparams | YAML identity params (`family` / `link` / `objective` / `tweedie_power` / `tweedie_variance_power` / `exposure_col` / `random_state`) are actuarial-rule-bearing (PRD rules 1, 4) -- never sampled, so a search suggestion can never break the rule. Ponytail ceiling: one default search space per `kind`; add a config-driven `search_space` when a portfolio needs model-specific ranges or extra params (`subsample` / `colsample_bytree` / `monotone_constraints` paired with v0.2 monotonic binning) |
| `tune_experiment` ships a final canonical `Run` (re-runs `run_experiment` with merged best params) | The actuary's downstream surface (`model_card` / `export_tariff` / `log_run`) takes a `Run`; re-running once with the best params keeps the tuned result on the canonical path with zero new plumbing. The merged params are `{**spec.params, **best.params}` so YAML identity params survive the search |
| `MissingTuneExtra` lazy import + optuna logging silenced to WARNING inside `_import_optuna` | mirrors `log_run`'s `MissingMLOpsExtra` shape (clear `tune` extra pointer); optuna logs every trial completion at INFO, which would flood `riskforge tune` output and pytest |
| `TuneResult.best_params` carries only the *sampled* hyperparams; identity params live on `Run.models[name].params` | the CLI summary line (`tuned <name>: k=v, ...`) shows just what the search changed; the canonical `Run` shows the full merged params (so `export_tariff` works unchanged) |
| CLI tune tests use per-test `pytest.importorskip("optuna")` (not module-level) | a module-level `importorskip("optuna")` in `test_cli.py` would skip profile / fit / compare / export-tariff tests under a core-only install -- unrelated to optuna. Per-test skip confines the `tune` extra dependency to the tune tests; `test_cli_help_lists_five_commands` runs without optuna because `riskforge tune` is always registered (the optuna import is lazy inside the command body) |
| Reproducibility test asserts `best_params == best_params` plus `best_values` within `rel=1e-9` | TPESampler(seed=...) choices are identical across runs; the Tweedie deviance carries ULP BLAS noise (3.66M +- 9e-7 observed, ~3e-14 relative). Strict value equality flaked; the rel-tol encodes the real reproducibility ceiling |
| `export_tariff` decomposes via `extract_tariff` + `recalibrate_for_total`, writes xlsx last | one structural extraction is reused by the roundtrip test, the recalibration, and the xlsx writer; no parallel code paths producing the same numbers |
| Reference level per categorical defaults to first-sorted (override via `reference=`) | deterministic, no data peek; the actuary's `reference=` override is the API the buckets need when the canonical base vehicle / region changes |
| Non-log-link GLM rejected (check reads `backend.link_instance.__class__.__name__`) | multiplicative decomposition is exact only for a log link; glum keeps `backend.link == "auto"` post-fit, so checking the resolved `link_instance` class is the only robust signal |
| `apply_tariff` treats unseen categorical level as factor 1.0 | glum's `cat_missing_method="fail"` raises at predict; the structural tariff treats missing as the reference (factor 1.0). The actuary's `reference=` is the override hook -- bail out via higher-level validation if a strict-unknown policy is needed |
| `feature_dtypes_` deprecated upstream; `mappings` sheet records `"category"` only for categoricals, blank for numeric | glum 3.x deprecated `feature_dtypes_` in favour of `categorical_levels_`; the latter has no dtype for numeric cols and the `dtype` column is informational -- kept blank rather than reaching back into X |
| `log_run` is one function (no classes); `MissingMLOpsExtra` raised via lazy import | PRD sec. 9 explicitly cut 5 mlflow classes; one function covers all of params/metrics/artifacts. Raises a clear pointer ("`uv sync --extra mlops`") when the extra is absent |
| `log_run` skips NaN/inf metrics silently | mlflow 3.x rejects NaN values; some `op_ratio_test` paths produce NaN when `pred_total==0`. Dropping them on the inside is the smaller diff than asking every caller to pre-filter |
| `log_run` uploads a directory under `<artifact_path>/<dir_name>` | `mlflow.log_artifacts` flattens contents under `artifact_path`; the explicit dir-name append preserves the caller's structure when a directory of artifacts (e.g. a plots dir) is logged |
| Tests use `sqlite:///<tmp>/mlflow.db` tracking uri | mlflow 3.x put the file store in maintenance mode (raises unless `MLFLOW_ALLOW_FILE_STORE=true`); sqlite is the guided replacement and clean per-test isolation |
| `ModelSpec` supports `glm` and `gbm` only (no `freqsev`) | FreqSev needs nested freq/sev sub-specs (recursive pydantic); M5 acceptance only needs an example config to run end-to-end -- a direct Tweedie GLM / GBM pair covers compare. Add the sub-spec path when a real config wants it |
| `model_card(fmt="html")` wraps escaped markdown in `<pre>` | PRD sec. 9 already cut `ModelCard.to_pdf` for weasyprint pain; a real markdown parser in core is heavy for a side artifact. Replace with a renderer in a `reporting`/`plot` extra when styling matters |
| `run_experiment` returns a `Run` (frozen pydantic) by default; `return_estimators=True` for fitted estimators | sklearn estimators are mutable and not pydantic-friendly; the metrics / calibration table / config fingerprint are the report surface, the estimators are only needed by M6 `export_tariff`. Opt in to the estimators to keep `Run` cheap / hashable |
| `_deviance_test` picks Poisson only for Poisson *frequency* fits, Tweedie p=1.5 otherwise | Pure premium convention (PRD sec. 5) -- a Poisson *severity* or *pure premium* fit has Gamma/Tweedie coverage mismatch; family detection by `spec.params["family"]` / `["objective"]` keeps it lazy without teaching the workflow about every objective |
| Fresh `rich.Console()` per CLI command (no module-level) | A module-level `Console()` captures the real `sys.stdout` at import time and bypasses `typer.testing.CliRunner`'s stdout patch -- tests would have to assert on files only. Per-call construction picks up the patched stream |
| `typer.echo(md)` for the model card body instead of `console.print(md)` | Rich parses `[bracket]` markup and our markdown params dict is rendered with backticks (safe) but `typer.echo` keeps the verbatim text documented in the model card (no markup / no truncation) |
| `make_strata` returns integer codes only; never splits itself | sklearn already has the splitters (`StratifiedKFold` / `StratifiedGroupKFold`); the helper just bridges "continuous y -> discrete codes" so the splitter accepts it -- duplicating splitter logic is the 6 splitter classes that PRD sec. 9 already cut |
| `temporal_split` returns positional integer index arrays (not a sklearn `BaseSplitter` subclass) | a single holdout doesn't need walk-forward folds; `TimeSeriesSplit` covers that -- one helper for the one-shape sklearn doesn't ship |
| `plots.py` never forces `matplotlib.use("Agg")`; tests do | forcing a backend globally would override a user's interactive backend; Agg is purely a render target for headless / CI |
| `plot_lift` defaults to `baseline="observed"` (portfolio observed PP) | lift = `observed_pp_decile / portfolio_observed_pp`; that's the actuarial convention and pairs naturally with `calibration_table` output as input |
| RiskGLM default `alpha=0.001` (not `0.0`) | Unpenalized glum is ill-conditioned on widest sklearn estimator-check designs (`check_sample_weight_equivalence_on_dense_data`); a vanishing ridge keeps it stable and is negligible for actuarial MLEs |
| Validation in `__init__` guarded with `isinstance(...)` for `RiskGBM` Tweedie power | Sklearn `check_do_not_raise_errors_in_init_or_set_params` feeds non-scalar smoke values to *every* param; a literal `__init__` raise breaks that contract. Re-validated in `_make_backend` so `set_params`-then-`fit` still raises |
| `FrequencySeverityModel` skipped from `parametrize_with_checks` | Meta-estimator with named special cols inside X; stylistically incompatible with the standard sklearn estimator contract exercised by those checks. Functional tests cover the contract |
| `_categorize_strings` casts object cols to `category` at module boundary | Glum silently ignores object columns (LinAlgWarning "Columns were ignored"; gives ill-calibrated fits); LightGBM rejects them outright. Casting at the boundary gives both backends their native categorical handling |
| `RiskGLM` / `RiskGBM` only strip `exposure_col`, not other special cols | Don't know the names of `claim_count` / `claim_amount` at this layer; the actuary drops them before a direct fit or wraps in `ColumnTransformer`. `FrequencySeverityModel` strips all three itself |
| `riskforge.models` not imported in `package __init__` | Pulls glum + LightGBM; user imports the heavy module explicitly |
| glum + lightgbm in core deps | GLM/GBM is the package's point; avoid ImportError wart |
| mlflow in `mlops` extra | heavy; only needed at M6; `log_run` imports lazily |
| Commit `uv.lock`, `.python-version` | reproducibility principle |
| Preprocessing built fresh | no arfs source located in `~/projects` |
| Defer Hydra | one config, no composition pain yet |
| matplotlib only v1 | headless PNG/PDF free; plotly v0.2 |
| Zensical docs at v0.3 | internal tool; docs not on critical path |