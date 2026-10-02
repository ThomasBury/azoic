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
   fingerprint (shape, columns, dtypes, categorical metadata, index, values),
   configuration/parameter snapshots, `log_run()` mlflow helper.

## 3. Module architecture (flat, no subpackages, no utils)

```
src/azoic/
  data.py          DatasetSpec (pydantic), load_data (pandas+pyarrow; s3 via fsspec)
  profile.py       profile_features() -> DataFrame; screen_features() -> keep/drop/review
  preprocessing.py AutoBinner, AutoGrouper (sklearn transformers; mapping_, set_mapping)
  models.py        RiskGLM, RiskGBM, FrequencySeverityModel
  metrics.py       gini, lorenz, calibration_table, stability_table, one_way_table, double_lift_table; re-exports sklearn deviances
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
is a numbered book under `examples/` (`_quarto.yml` + chapter `.qmd` sources
plus a shared `_shared.qmd` include) and is linked rather than restyled.

## 4. Model API conventions

### Special columns travel inside X (not as fit kwargs)
sklearn's `GridSearchCV`/`cross_val_score` will not forward
`fit(X, y, exposure=...)`. So:
- Estimators take `exposure_col: str` and pop that column from X inside
  `fit`/`predict`.
- `FrequencySeverityModel` takes `exposure_col`, `claim_count_col`,
  `claim_amount_col`.

This keeps full sklearn compatibility (pipelines, grid search, CV).

### Estimator response units
Every estimator takes pure-premium rate targets in `fit` and `score` and
returns rates from `predict`. `FrequencySeverityModel.fit(X)` may omit `y`
because its outcome columns travel inside `X`; a supplied `y` must be a
finite one-dimensional rate equal to `claim_amount / exposure`.

### Backend wrappers expose explicit params (no `**kwargs`)
LightGBM `**kwargs` break `get_params`/sklearn (per LightGBM docs). `RiskGBM`
declares each used param explicitly.

## 5. Actuarial correctness rules (do not violate)

1. **Exposure is a weight, not an offset** when modelling pure premium.
   Pure premium GLM: `y = claim_amount / exposure`, `sample_weight=exposure`.
   Estimator targets, scores, and predictions use this rate unit. Use log-link
   with `offset=log(exposure)` ONLY when `y = claim_amount`
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
   aggregated into single blocks before integration so Gini is independent of
   row order within ties. `gini = 1 - 2*auc` is twice the signed area from the
   curve to the diagonal and can be negative, including with crossing curves;
   the tie-corrected polygonal calculation is numerically identical to the
   Frees-Meyers-Cummings midrank closed form. Never infer calibration from
   Gini; always pair it with `calibration_table` + O/P ratio. The Lorenz
   plot optionally overlays the hindsight observed-rate oracle curve and
   shades the area whose signed value is half the Gini. Observed-rate ranking
   recovers exposure-weighted inequality Gini, a hindsight bound generally
   below one; it does not measure calibration.
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
  Markdown model card, and CLI commands `profile`, `fit`, `compare`,
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
  No Azoic version has been publicly released; the site documents current
  behavior without a version-migration page.
  *Done when the documented first model and checkout YAML run,
  `just docs-build` is strict-green, generated HTML contains navigation, tables,
  highlighted code, Arithmatex wrappers, and both MathJax scripts, and project
  checks remain green.*

- **M9 — contract and residual correctness (v0.4.1)**: standardize estimator
  prediction and scoring units; validate a supplied rate target in
  `FrequencySeverityModel`; correct actual-versus-predicted and residual plots
  to compare observed and predicted rates; and reconcile stale CLI/reporting
  documentation. *Done when contract tests, residual-unit tests, `just check`,
  and `just docs-build` pass.*
- **M10 — configuration-driven tuning**: add optional typed tuning configuration
  with trial count, calibration penalty, and per-model parameter distributions.
  Preserve existing defaults when it is absent. Reject identity-defining
  parameters; nested frequency-severity tuning remains out of scope. *Done when
  YAML validation, reproducibility, explicit CLI precedence, and untouched
  outer-holdout tests pass.*
- **M11 — temporal stability diagnostics**: add `stability_table` with exposure,
  observed and predicted totals, O/P, Gini, deviance, and \(D^2\) by period.
  Reject missing periods and reconcile period totals to the full input. Rolling
  refit orchestration and a new plotting backend remain out of scope. *Done when
  seeded synthetic temporal tests and project checks pass.*
- **M12 — protected-group audit**: add protected columns to the dataset contract,
  exclude them from model features, and retain them for held-out group
  calibration. Surface evidence in results and model cards without universal
  fairness thresholds or legal conclusions. Reuse `calibration_table`; add no
  fairness dependency. *Done when leakage-prevention and subgroup-to-portfolio
  reconciliation tests pass.*
- **M13 — interpretation recipes**: document sklearn PDP/ICE and LightGBM native
  contributions using fitted Azoic estimators and pipelines. Explain
  correlated-feature and causal-interpretation limits. Add no Azoic wrapper and
  no DALEX/SHAP dependency. *Done when examples run on synthetic data and the
  strict docs build passes.*
- **M14 — documentation parity and release hardening**: document temporal
  stability diagnostics alongside the existing task recipes, remove obsolete
  roadmap language from generated API documentation, and separate release
  validation from trusted publication. Build, check, and smoke-test both
  distributions before handing the exact artifacts to the least-privilege
  publishing job. Add no second tutorial, dependency, or Python interface.
  *Done when `just check`, `just docs-build`, `uv build`, and isolated wheel and
  source-distribution CLI smoke tests pass and the Pages deployment is green.*
- **M15 — first public release**: publish the validated `azoic==0.4.1`
  distributions through PyPI trusted publishing from a `v0.4.1` GitHub release.
  M16–M42 and the separate tutorial review are prerequisites; rebuild and revalidate the corrected source using M14's
  distribution checks before publication. Recording pending milestones does
  not authorize publishing.
  *Done when PyPI exposes the release, a fresh isolated install reports version
  `0.4.1` and all five CLI commands, and the release and documentation workflows
  are green.*

- **M16 — preserve the experiment holdout** — **completed 2026-09-05**:
  immutable `Run.train_indices` and `Run.test_indices` record actual fit and
  evaluation positions. Tutorial diagnostics, training calibration, and CLI
  distillation reuse them; CLI export rejects changed input fingerprints.
  Exact membership, raw-metric reproduction, outer-tuning-boundary, CLI
  distillation, strict docs build, and full tutorial-render checks pass.
  See `PROGRESS.md` for acceptance evidence.
- **M17 — reject inconsistent frequency-severity outcomes** — **completed
  2026-09-05**: standalone fitting enforces the workflow's exposure/count/amount
  contract before rate division, cloning, or component fitting. Invalid outcomes
  fail with and without a supplied rate across direct and pipeline fits; workflow
  checks, valid-data weights, outcome-free prediction, the full suite, and strict
  docs build pass. See `PROGRESS.md` for acceptance evidence.
- **M18 — faithful tariff bins and similarity groups** — **completed
  2026-09-05**: labels describe existing lower-inclusive bin assignments;
  nominal categories reuse adjacent-risk merging after stable risk sorting.
  Independent workbook boundary application, aggregate-risk/credibility/ordered
  adjacency checks, the full suite, strict docs build, and a fresh tutorial
  refit pass. Migration guidance requires regenerating fitted models and
  workbooks together. See `PROGRESS.md` for acceptance evidence.
- **M19 — complete missing-value diagnostics** — **completed 2026-09-05**:
  weighted quantiles use observed grouping values and their matching weights;
  missing numeric segments retain their totals and remain visible in one-way
  plots. Missing-exposure invariance across shared callers, empty/all-missing
  handling, weight validation, total reconciliation, visible missing-group
  checks, the full suite, and strict docs build pass. See `PROGRESS.md` for
  acceptance evidence.
- **M20 — valid diagnostic references and residual scales** — **completed
  2026-09-05**: claim-free experiments report undefined test D²; the oracle ranks
  observed rates; logarithmic residual views use native symmetric log axes with
  correctly positioned density cells. Claim-free reporting/tuning, constant and
  ordinary D² baselines, unequal-exposure/tied-rate oracle coordinates, actual
  signed-density rendering, the full suite, and strict docs build pass. See
  `PROGRESS.md` for acceptance evidence.
- **M21 — correct actuarial explanations** — **completed 2026-09-05**:
  every tutorial candidate reports training O/P and uses a frozen training-only
  factor, with labelled raw/adjusted holdout diagnostics. Double-lift compares
  predictions with observations; residual guidance separates additive and
  multiplicative errors; concentration and inequality Gini are distinct.
  Numerical examples, training-only factor checks, the full suite, strict
  documentation build, and full tutorial rendering/visual inspection pass.
  See `PROGRESS.md` for acceptance evidence and the M15 handoff.

### M22 — show what fitted preprocessing does (completed 2026-09-06)

Lead with the direct binned/grouped GLM baseline, raw GBM benchmark, and structured
GBM teacher. Preserve parameters, tree/similarity settings, and stored partitions.
Show fitted intervals/memberships with training policy counts, exposure, claim counts,
and observed pure premium. Use frozen groups for held-out GLM one-ways; illustrate
fixed-policy age steps beside raw-age composition effects. Explain uncertain cuts,
unadjusted grouping loss rates, credibility floors, and no monotonic guarantee.
Preserve ordered-category one-way order, observed groups, and missing totals.
Move frequency–severity fitting, comparison, and reporting to an executable appendix.
Acceptance: ordered/unused/missing regression; totals, fixed-policy invariance,
within-bin equality, exact partitions, frozen mappings, positive predictions,
raw metric reproduction, adjusted training O/P one, Gini invariance, and workbook
agreement. Full tutorial/appendix render and visual inspection, `just check`,
`just docs-build`, and `git diff --check` must pass.

All M22 acceptance checks passed; see `PROGRESS.md` for full-render, regression,
visual, and unchanged-metric evidence. The subsequent presentation cleanup
replaces the manual fixed-policy curve with raw-value one-ways for both ages and
a link to the existing sklearn PDP/ICE recipe. Fitted-group views remain supporting
diagnostics; no training inputs or settings change. M23 is also complete; M15 is next.

### M23 — evaluate the exported tariff against claims (completed 2026-09-06)

Distil the structured teacher on training rows with copied preprocessing. Export
with `recalibrate=False` and training metadata. Apply workbook factors using the
existing recipe to fitted-pipeline-transformed features; no standalone loader.
Check workbook/student agreement on train/test at existing tolerance. Finish with
four rows: direct GLM, raw GBM, structured teacher, applied workbook; show weighted
Tweedie deviance at 1.5, D², concentration Gini, O/P, predicted total claims, and
common observed claims/exposure. Add calibration panels, overlaid Lorenz curves,
and age comparisons at raw values, supported by identical-training-bin views.
Separately show metrics adjusted
by each model's own frozen training O/P (including workbook training predictions);
the workbook adjustment is an external multiplier. Separate teacher/student deviance
and total-ratio fidelity from claims performance. Describe gains/losses without
assuming distillation worsens performance or claiming superiority from one split.
Repeat tutorial/visual, partition/mapping/scaling/metric, suite, docs, and diff checks.
No new dependencies, public interfaces, binning algorithm, or automated selection.

All M23 acceptance checks passed; see `PROGRESS.md` for the four-candidate
claims results, separate fidelity, training-only scaling regression, fresh
32-cell tutorial render, visual inspection, full suite, and strict docs build.

### M24 — ordered tutorial series (completed 2026-09-11)

Convert `examples/` into a numbered Quarto book so the whole library feature
set has executable coverage. A shared `_shared.qmd` include carries imports,
deterministic fetch/cache loading, config builders, and helpers; chapters refit
their own models (no fitted estimator persists across chapters). Ordered
chapters: index; portfolio; experiments; diagnostics; scoring and tariff;
reporting and operations; frequency–severity appendix; tuning; synthetic
temporal stability; protected-group audit; and manual tariff recipes.
CI renders the book directory; the old single-page URL expires deliberately.

The main reading path ends at scoring and tariff review; operations and later
modelling recipes are optional. Shared setup is hidden, tutorial helpers are
identified, and chapters create their own reports/workbooks. Reporting logs
only artifacts generated by that chapter; evaluated CLI exports do not consume
holdout outcomes for recalibration. Full sequential rendering and independent
chapter execution are separate checks; the focused automated reporting smoke
uses only synthetic cached input and a fresh process. Cache invalidation for
claim-cap/cleaning changes remains an explicit reader responsibility.

Acceptance: `just check`, `just docs-build`, and full book render pass; generated
`_book`/artifacts stay ignored; the tuning chapter leaves the outer holdout
untouched. `PRD.md`, `AGENTS.md`, `PROGRESS.md`, `docs/`, `justfile`, and the CI
docs workflow are updated together.

### M25–M30 — tutorial usefulness and actionability (planned 2026-09-13)

The existing book covers the feature set; this revision teaches readers how to
adapt it and interpret its outputs. The intended reader knows Python DataFrames
and train/test separation; introduce actuarial modelling terms before relying
on them. Keep the current chapters, default presentation, public APIs, and
dependencies. Reuse the network-free first-model guide rather than adding a
second introduction. No deployment, persistence framework, or standalone Excel
scorer is part of this work.

Implement one green milestone per session in this order:

- **M25 — executable examples and labels:** repair the shipped YAML's
  config-relative data path and matching guide/reference snippets; test that
  exact config; correct protected age-band labels without changing membership.
- **M26 — priced population:** explain column meanings/units and reconcile
  sequential policy exclusions, exposure, claims, and the separate claim-cap
  impact. Preserve cleaning decisions and retain an ignored audit alongside
  the cleaned cache as `cleaning_audit_v1.csv`, rebuilding both from raw cached
  inputs if either is absent. Delete both derived caches after cap/rule changes.
- **M27 — adaptable experiment:** expose executable configuration in teaching
  order, define GLM/GBM/Tweedie roles, defer teacher details, and show a minimal
  own-portfolio adaptation. Preserve the existing three candidates and verify
  visible config parity with shared setup.
- **M28 — worked policy price:** show one outcome-free held-out policy's fitted
  levels, direct-workbook factor multiplication, raw/adjusted rates, and expected
  cost. Verify model/workbook/scoring agreement with the training multiplier
  external to the raw workbook.
- **M29 — component diagnostics:** show raw frequency, severity, their product,
  and correctly weighted held-out calibration for both alternatives. Explain
  their comparison with direct Tweedie; keep MLflow/report writing in operations.
- **M30 — interpretable tuning:** declare bounded custom spaces and an untuned
  baseline on the same subset/outer partition, explain penalty scale, and compare
  actual gains without requiring improvement. Preserve nested selection and
  the tuned scoring/export/CLI handoff.

Acceptance combines focused synthetic regressions, exact-example execution,
`just check`, strict docs, affected-section visual review, and full book render.
Changes to chapter setup additionally require isolated execution with only
declared inputs. No generated artifacts enter version control. All milestone
checklists, exact defaults, evidence, and resume checkpoints live in the
[tutorial improvement plan](PROGRESS.md#tutorial-improvement-plan--2026-09-13).
`PROGRESS.md`'s **Current focus** overrides earlier historical release handoffs;
after M30, stop and return to the separate M15 release task.

The completed 2026-09-05 priorities and regression criteria remain in the
[correctness remediation plan](PROGRESS.md#correctness-remediation-plan--2026-09-05).
Preserve that evidence; the new tutorial plan does not reopen completed work or
expand the optional roadmap below.

### M31–M32 — fail-closed hardening (planned 2026-09-14)

A post-tutorial review found eight places where invalid inputs or configuration
are silently accepted, producing valid-looking but wrong numbers (fail-open).
All were reproduced against the green M25–M30 baseline. Fix them by validating
at the trust boundary and raising (or warning, where noted) instead of
correcting silently. No public API additions, no new dependencies, no
behaviour change for valid inputs. Implement one green milestone per session:

- **M31 — diagnostics and exposure weighting:** validate finite/non-negative
  inputs in `metrics._as_arrays` (and `double_lift_table`'s `pred_b`,
  `calibration_table`'s `claim_count`), mirroring `stability_table`'s
  strictness while keeping `y_pred` sign-permissive (Poisson GBM zeros are
  legitimate); make `_pop_weight` raise in `fit`/`score` when a configured
  `exposure_col` is absent from X and no explicit `sample_weight` is given
  (`predict` stays permissive — new data need not carry exposure).
- **M32 — configuration, labels, scoring, and recorded params:**
  `DatasetSpec` special-column names must be distinct; `AutoBinner`/
  `AutoGrouper` raise on unknown requested columns and unknown strategies
  (similarity grouping without a target raises, or warns if estimator checks
  require otherwise); `ModelSpec` warns on ill-posed frequency/severity
  component families and `FrequencySeverityModel.predict` warns when it clips
  negative component predictions; `AutoGrouper` synthetic `group_{i}` labels
  are namespaced against real levels and `one_way_table` keeps genuine `"nan"`
  strings distinct from missing; `RiskGBM.score` raises with a `scoring=`
  pointer for objectives outside the deviance map (L2 aliases map to power 0);
  `ModelSpec.build` raises on an `exposure_col` contradicting `spec.exposure`
  and recorded params come from a single `effective_params` source shared with
  `build`.

Acceptance per milestone: focused synthetic regressions for each fixed
reproduction, `just check`, `git diff --check`. Checklists, decisions, and
evidence live in [PROGRESS.md](PROGRESS.md#fail-closed-hardening-plan--2026-09-14).

### M33 — post-hardening fixes (2026-09-19)

Follow-up to the committed M31/M32 hardening; fixes verified with runnable
probes in a fresh review:

- **Models:** `_pop_weight` validates resolved weights (finite,
  non-negative, not all-zero — LightGBM accepts negative/NaN weights
  silently); the missing-`exposure_col` raise only fires without an explicit
  `sample_weight` (explicit weights are a first-class override).
- **One-day exposure floor:** `MIN_EXPOSURE = 1/366` (0.1% relative
  tolerance for day-count representations) enforced at the portfolio
  boundary, in `FrequencySeverityModel.fit`, on popped exposure columns, on
  calibration/one-way segment sums, and in tariff recalibration;
  `min_exposure` requires `>= MIN_EXPOSURE` and a real exposure column.
  Ranking curves (gini/lorenz) keep zero-weight rows legal.
- **Workflow:** `frequency_severity` specs forward `params` to the
  constructor and raise on conflicts with the dataset special columns, so
  recorded params can never drift from the fitted estimator.
- **Edges:** `plot_lorenz` accepts non-string model keys; `AutoGrouper`
  rejects `max_groups < 1`; `screen_features` survives an empty profile;
  `DatasetSpec` rejects empty optional special names.

Acceptance and evidence live in
[PROGRESS.md](PROGRESS.md#m33--post-hardening-fixes--2026-09-19).

### M34–M39 — source audit remediation (planned 2026-10-01)

The source audit at `d6f7cae` reproduced silent prediction, weighting,
calibration, diagnostic, and provenance defects despite a green 839-test
baseline (4 upstream skips). Deliver M34 → M35 → M36 → M37 → M38 → M39,
one independently green milestone per session. M34–M39 completed 2026-10-01.

Prefer public sklearn `validate_data`, `check_array`, and
`check_consistent_length` over custom schema/array validation. Schema-only
DataFrame validation preserves native categoricals but does not check numeric
targets or weights. Retain small domain guards for strict one-dimensional
vectors, optional special-column schemas, exposure floors, sign constraints,
and outcome consistency. Reuse existing `_pop_weight` / `_as_arrays`; add no
validation framework, dependency, subpackage, or compatibility shim.

- **M34 — estimator schema, targets, and scoring weights:** reject changed
  model-feature names/order in prediction/scoring; validate finite GBM targets
  on DataFrame inputs; give frequency–severity scoring the existing weight and
  override rules. Keep prediction without exposure and native categorical/NaN
  feature support. Use glum's public distribution import and correct sklearn's
  declared minimum to cover `validate_data` (introduced in 1.6). Strict 1D
  targets intentionally reject sklearn's column-vector flattening convention;
  record that conformance check as an expected failure with a direct regression.
- **M35 — configuration, preprocessing, and input inspection:** forbid unknown
  `DatasetSpec` fields, require/validate configured preprocessing weights,
  validate bin counts and fitted mapping overrides, profile boolean features,
  and preserve URI strings in the profiling CLI.
  Configured exposure/claim-count columns must exist and be finite; exposure
  retains the one-day floor and claim counts must be non-negative. No configured
  exposure means explicit unweighted operation; target-column/y fallback stays.
  Overrides replace the entire mapping, accept only currently mapped columns,
  and validate edges/vocabularies before replacing state.
- **M36 — training-only tariff calibration:** default CLI recalibration uses
  stored training positions for direct and distilled exports; validate vector
  outcomes before recalibration. Preserve explicit library calibration frames
  and structural exports. Separate frame objects do not prove disjoint rows;
  direct distillation callers own that independence contract, while CLI tests
  verify stored partitions.
- **M37 — stable tariff arithmetic and literal workbook labels:** compute
  tariffs in log space, reject unrepresentable factors/rates, retain zero-total
  recalibration, and write user text as literal Excel strings with unchanged
  typed labels and the existing three-sheet schema.
- **M38 — complete and unambiguous diagnostics:** reuse numeric validation in
  plots, prevent double-lift label collisions and degenerate exposure groups,
  and retain a real group for constant unweighted predictions. Preserve zero
  weights for ranking and meaningful missing groups.
- **M39 — reproducible results and comparable evaluation:** fingerprint full
  categorical metadata, snapshot configuration/parameters, and warn on mixed
  evaluation contexts while preserving descriptive comparisons and table shape.
  Include unused vocabulary, category dtype/order, and the ordered flag; later
  caller mutations must not rewrite recorded config or nested parameters.
  Public containers remain mutable. Compare holdout positions as sets and warn
  once naming affected runs when fingerprints or target/exposure definitions
  differ as well. Older category fingerprints need fresh evaluation.
  Keep small stdlib logger cleanup within this milestone.

Interfaces retain their signatures, except the profiling CLI accepts URI
strings correctly. On implementation, invalid inputs will raise, comparisons
can emit a warning, and category-aware fingerprints will intentionally change.
The numerical regression cases, complexity/effort estimates, checkpoints, and
exact acceptance commands
are recorded in [PROGRESS.md](PROGRESS.md#source-audit-remediation-plan--2026-10-01).
CI/CD and documentation/tutorial review are separate; publication is not part
of this plan.

### M40–M42 — prerelease fixes (2026-10-02)

Two exploratory installed-wheel runs reproduced 88 failures, chiefly string
handling and read-only pandas array mutation, without tracked changes. Deliver
M40 → M41 → M42 → M15, one independently green milestone per session.

- **M40 (completed 2026-10-02):** require pandas ≥3.0, recognize default `str`, nullable string, and
  object predictors through the shared categorical conversion. Preserve numeric
  columns, declared category metadata, and caller frames; keep Copy-on-Write.
  Correct mutating tests and deprecated categorical construction; regress
  category influence, tariff extraction, category order, and unused levels.
  Add a runtime-only distribution smoke script for GLM/GBM fit/score, categorical
  influence, installed imports, and version consistency. Validate wheel and
  sdist outside the checkout with independently resolved dependencies and CLI
  help. Correct migration/model-choice guidance. Require full suite, strict
  docs, exact first-model categorical influence, full tutorial render, and
  isolated scoring-chapter render. pandas 2 support ends; estimator signatures
  and actuarial units stay unchanged.
- **M41:** align documentation with training-only CLI tariff recalibration,
  caller-selected library calibration frames, DatasetSpec exposure routing and
  conflicting non-null override errors, standalone HTML dashboards, and
  absolute-rate lift. Keep prose changes minimal, inspect rendered pages and
  verify examples/local references against source.
- **M42 (completed locally 2026-10-02):** add Python 3.12 PR/main validation with read-only contents permission,
  all locked extras/groups, Ruff/Ty/pytest/strict docs/distribution checks and
  M40 artifact smokes. Reuse action pins. Keep tutorial render in Pages, add
  fixed `pages` concurrency with cancellation, and lock dependency sync.
  Local workflow/shell validation, full checks, strict docs, builds, and installed
  artifact smokes passed. Pushed PR checks and Pages cancellation remain
  unverified and need separate authorization.

Every unit passes `just check` and `git diff --check`; documentation also passes
`just docs-build`. M15 remains a separate trusted-publisher/release review;
private settings, tagging, and publication are separately authorized. Execution
checklists and checkpoints live in [PROGRESS.md](PROGRESS.md#prerelease-fixes--2026-10-02).

### M43–M44 — focused documentation revision (2026-10-02)

The accepted review calls for focused corrections, then tutorial progression;
no wholesale rewrite, API change, dependency, theme, deployment feature, or
standalone Excel scoring engine. Deliver M43 → M44 → M15, one milestone per
session. This order supersedes the older release handoffs above.

- **M43 (completed 2026-10-02):** make checkout installation, verification, first-model execution, and
  extras consistently use `uv`; separate contributor checks. Select scoring
  inputs from `run.feature_names` plus configured exposure, with identifiers
  alongside output. Use `.iloc` for temporal positions. State the one-day
  exposure minimum (1/366 with 0.1% tolerance) and complete the workflow metric
  inventory with `d2_test`, its observed-mean null, and undefined cases.
- **M44 (completed 2026-10-02):** teach portfolio → GLM/raw-feature GBM → diagnostics → scoring → direct
  GLM workbook. Introduce the structured teacher at optional distillation and
  explicitly construct it for tuning using current settings/preprocessing.
  Explain one numeric bin and categorical grouping before the optional full
  nine-feature inspection; fold implementation checks while retaining assertions.
  Explain raw/adjusted prediction uses once and label outputs. Interpret the
  first model's actual Gini/O/P honestly. Show CLI commands and hide subprocess
  plumbing. Keep existing chapters, mathematical explanations, and optional
  frequency–severity, tuning, temporal, protected-group, and manual revision lessons.

Acceptance: execute corrected snippets; regress extra metadata at scoring and
non-default indices at temporal selection; run existing tutorial checks,
`just check`, strict `just docs-build`, and diff checks. Tutorial execution
changes require a fresh full-book render and isolated scoring, reporting,
tuning, and temporal chapters. Sources only; generated artifacts stay ignored.
Execution record: [PROGRESS.md](PROGRESS.md#focused-documentation-revision--2026-10-02).

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
  with real adjacency; remote MLflow waits for an endpoint; SageMaker waits for
  a named target environment.

Demand-gated decisions below are not pending milestones:

- **Exact fused/group lasso** — first test existing monotonic preprocessing and
  glum quadratic difference penalties on a real unstable ordered factor.
- **Second-stage residual modelling** — require an out-of-fold correction design
  and a stable untouched-holdout improvement over direct GBM.
- **Large-loss tail modelling** — require claim-level severities and a defined
  capping, censoring, or excess-loading objective.
- **Guidewire adapter** — the existing workbook covers manual entry; require a
  concrete importer contract before integration work.
- **ALE, SHAP, or DALEX** — add an optional explanation extra only when PDP/ICE
  or native contributions are insufficient.

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
| plotly dual diagnostic backend | doubles test surface | existing Plotly comparison dashboard; add diagnostic charts only for a real business need |
| Textual, PowerPoint, ALE, geopandas | YAGNI for v1 | cut until concrete demand |
| `pydantic AND dataclasses` | overlap | pydantic only |
| `ModelCard.to_pdf` | windows weasyprint pain | Markdown-only `model_card()` |

## 10. Decisions log

| Decision | Rationale |
|---|---|
| Python 3.12 (not 3.14) | glum/lightgbm wheels confirmed for 3.12; 3.14 too new |
| Preprocessing built fresh (not ported from arfs) | no arfs source located in `~/projects` |
| Defer Hydra | one config, no composition pain yet; Typer flags suffice |
| matplotlib diagnostics by default | headless PNG/PDF free; Plotly remains limited to the comparison dashboard until interactive charts have a business need |
| Zensical site | task-first navigation and generated tutorial HTML; default theme; JavaScript limited to Zensical's official MathJax helper and CDN runtime |
| glum + lightgbm in core (not extras) | GLM/GBM is the package's point; avoid ImportError-on-import wart |
| mlflow in `mlops` extra (not core) | heavy; only needed at M6; `log_run` imports lazily |
| No additional OOT workflow helpers | `time_col` is optional and already accepts any sortable period (including year-month); a dataset without an ordered period cannot support OOT validation |
| Commit `uv.lock` + `.python-version` | reproducibility principle |
| freMTPL2 rather than Swedish motorcycle for M8 | one portfolio covers direct Tweedie, frequency-severity, preprocessing, evaluation, and tariff export |
| Commit only tutorial `.qmd` book sources | executable prose is durable; data, caches, and rendered outputs are reproducible artifacts |
