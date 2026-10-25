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

### Rule ownership and maintenance baseline (M49)

This map records the M49 baseline and subsequent enforcement changes; it does
not introduce a validation framework. Amounts are aggregate currency, exposure is
policy-years, and model predictions are currency per policy-year unless a component
unit is stated. `data.py` owns `MIN_EXPOSURE = 1/366` and `EXPOSURE_FLOOR`
(the same floor with 0.1% day-count tolerance). Schema checks alone do not validate
outcome values. Run an evidence node below with `uv run pytest NODE`; the full
baseline is `just check`.

| Rule and units | Current owner and enforcement boundaries | Deliberate exceptions or limits | Runnable evidence (pytest node) |
| --- | --- | --- | --- |
| Portfolio outcomes: finite, non-negative amounts/counts; row exposure at least one day; counts and amounts zero together | `data._validate_outcomes` validates aligned 1D vectors for `workflow._validate_portfolio` (ordinary/tuned entry) and `FrequencySeverityModel.fit` | `load_data` checks required columns only. Count/amount consistency applies when counts are configured. Schema, supplied-rate and severity checks stay at their boundaries. | `tests/test_workflow.py::test_run_experiment_rejects_inconsistent_claim_rows`; `tests/test_models.py::test_freq_severity_rejects_invalid_outcomes_before_components` |
| Exposure versus explicit model weights | `models._pop_weight` strips configured exposure; validates aligned, finite, non-negative, nonzero-total weights in fit/score; applies row floor to popped exposure | Explicit `sample_weight` overrides the column and has no day floor; zero entries are legal with positive total. Prediction can omit exposure. | `tests/test_models.py::test_explicit_sample_weight_is_not_floored`; `tests/test_models.py::test_m34_scoring_weight_contract`; `tests/test_models.py::test_popped_exposure_below_one_day_raises` |
| Pure-premium rate targets and scores | Workflow divides amount by exposure; model `_validate_target` checks finite, aligned 1D targets; FSM checks supplied rate equals amount/exposure | Aggregated amounts belong in diagnostic inputs, not estimator targets. Direct wrapper target support also depends on backend family. | `tests/test_workflow.py::test_run_records_exact_fit_and_holdout_positions`; `tests/test_models.py::test_freq_severity_fit_rejects_aggregate_or_mismatched_target`; `tests/test_models.py::test_m34_invalid_targets_rejected_before_backend` |
| Frequency (claims/year), severity (currency/claim), product (currency/year) | `FrequencySeverityModel.fit` clones components; frequency uses count/exposure weighted by exposure; severity filters positive-count rows and uses amount/count weighted by count | Severity claim-count weights are explicit weights, never exposure. Claim-free training cannot fit severity; claim-free holdouts remain evaluable. | `tests/test_models.py::test_freq_severity_severity_fit_is_filtered`; `tests/test_models.py::test_freq_severity_rejects_portfolio_without_severity_observations`; `tests/test_tune.py::test_tuning_completes_with_claim_free_inner_and_outer_holdouts` |
| Feature schema and exclusion of outcomes, times and protected columns | `DatasetSpec`, `ExperimentConfig.feature_columns`, workflow column selection/drop; model `_store_fit_meta` / `_check_model_features`; preprocessing `_validate_transform_input` | Standalone GLM/GBM only strip configured exposure. Other outcome columns must be removed by callers. Optional specials may be absent at prediction; predictor names/order must match. | `tests/test_models.py::test_m34_model_predictor_schema`; `tests/test_workflow.py::test_protected_audits_use_outer_test_and_never_fit_columns`; `tests/test_preprocessing.py::test_preprocessing_transform_tolerates_absent_special_columns` |
| Supervised preprocessing outcomes and credibility floors | `preprocessing._column_array`, `_resolve_target`, `_check_controls`, `_fit_tree`; configured amount/exposure becomes a rate; counts constrain credibility, never learning weights | Explicit `y` fallback is already a rate. Tree/similarity need outcomes; quantile/rare remain alternatives. Preprocessing exposure has a row floor, unlike grouped diagnostics. | `tests/test_preprocessing.py::test_preprocessing_preserves_target_fallback_and_exposure_units`; `tests/test_preprocessing.py::test_weighted_numeric_tree_matches_replicated_exposure`; `tests/test_preprocessing.py::test_weighted_native_partitions_match_replicated_exposure` |
| Missing predictors and mapping interpretation | GBM routes missing values natively; binner/grouper store `mapping_`, `missing_`, `closure_` and categorical vocabulary; mapping overrides validate before committing state | Tree intervals use upper-inclusive `<=`; quantile/manual intervals are lower-inclusive. Changed native mappings require an explicit missing destination. Grouper unseen levels route with missing levels; GLM has no native missing routing. | `tests/test_models.py::test_m34_gbm_keeps_native_missing_features`; `tests/test_preprocessing.py::test_native_numeric_thresholds_and_roundtrip_use_less_equal`; `tests/test_preprocessing.py::test_changed_native_mapping_requires_explicit_missing_transactionally`; `tests/test_preprocessing.py::test_native_categorical_missing_unseen_and_frozen_vocabulary` |
| Fitted state, cloning and parameter validation | Models guard `backend_` / `freq_`; transformers guard `mapping_`; sklearn cloning and fitted metadata remain module responsibilities | M54 constructors store controls unchanged; fit validates power/constraints, including after `set_params`. Backend internals and private override hooks carry no compatibility promise. | `tests/test_models.py::test_sklearn_compatible`; `tests/test_preprocessing.py::test_sklearn_compatible`; `tests/test_models.py::test_riskgbm_invalid_power_at_fit_after_set_params` |
| Ranking versus calibration | `metrics._as_arrays` validates diagnostic vectors; `_concentration_curve` integrates tied predicted scores; `op_ratio` compares sum(amount) with sum(rate × exposure) | Ranking accepts zero/sub-day weights and returns zero Gini for zero total claims/exposure. Positive prediction scaling preserves ranking but changes O/P. | `tests/test_metrics.py::test_tied_score_gini_has_hand_calculated_area_and_separate_calibration`; `tests/test_metrics.py::test_gini_zero_total_claims_or_exposure` |
| Grouped diagnostic exposure (years) and count totals | `calibration_table`, `one_way_table`, `double_lift_table` floor each segment's total exposure | Zero/sub-day rows can contribute to a valid segment. `stability_table` instead enforces the row floor. Optional calibration counts must be aligned finite, non-negative 1D vectors; they do not impose portfolio count/amount consistency. `[3, 4]` in one segment sums to seven. | `tests/test_metrics.py::test_grouped_diagnostics_floor_segment_totals_instead_of_rows`; `tests/test_metrics.py::test_calibration_table_rejects_zero_exposure_segments`; `tests/test_metrics.py::test_calibration_counts_reject_broadcasting_and_invalid_vectors`; `tests/test_metrics.py::test_calibration_counts_are_positional_segment_totals`; `tests/test_metrics.py::test_stability_table_rejects_sub_day_exposure` |
| Deviance and D²: weighted rates, fixed power 1.5 for experiment/stability comparisons | Shared `metrics._tweedie_scores` for workflow `_evaluate_split` and `metrics.stability_table`; deviance functions are upstream sklearn re-exports | Estimator scores use their family/objective power. Workflow warns and yields inf/NaN for nonpositive predictions; stability rejects them. D² uses the evaluated period's observed-mean null; zero null deviance gives NaN. | `tests/test_metrics.py::test_deviances_reexported`; `tests/test_workflow.py::test_run_deviance_is_exposure_weighted_tweedie_power_1_5`; `tests/test_workflow.py::test_temporal_test_d2_matches_period_baseline`; `tests/test_workflow.py::test_run_experiment_handles_clipped_zero_predictions_and_ordered_protected_cols` |
| Evaluation boundaries and holdout membership | `validation.temporal_split` keeps equal timestamps together; workflow records positional splits; tuning derives inner splits only from outer training and evaluates final models on outer test | Protected diagnostics are descriptive outer-test evidence. Comparison warns on incompatible data/target/exposure/holdout contexts. Distillation callers must supply disjoint observations; object identity cannot establish independence. | `tests/test_validation.py::test_temporal_split_keeps_equal_timestamps_on_one_side`; `tests/test_validation.py::test_temporal_split_rejects_missing_times_and_empty_cutoff_partitions`; `tests/test_tune.py::test_tuning_does_not_inspect_outer_test_outcomes`; `tests/test_reporting.py::test_comparison_warns_once_for_mixed_evaluation_contexts` |
| Result snapshots and audit limits | Workflow `_assemble_run` deep-copies config and effective explicit params, fingerprints the canonical frame and records split positions once per final run; lazy package exports keep imports light | Frozen result attributes contain mutable public containers. M55 records full wrapper/preprocessing constructors, runtime versions and effective tuning once per final run; empty historical metadata stays unrecorded. This is audit evidence, not portable replay or backend fitted state. Caller owns data, environments and fitted-model storage. | `tests/test_workflow.py::test_run_snapshots_caller_configuration_and_nested_params`; `tests/test_workflow.py::test_data_fingerprint_covers_categorical_metadata`; `tests/test_init.py::test_package_exports_are_lazy_and_discoverable`; `tests/test_workflow.py::test_final_provenance_covers_defaults_components_and_independent_snapshots`; `tests/test_workflow.py::test_historical_results_keep_provenance_unrecorded`; `tests/test_tune.py::test_tuning_provenance_records_effective_controls_once_per_final_run`; `tests/test_reporting.py::test_model_card_has_compact_and_historical_provenance`; `tests/test_mlops.py::test_log_run_separates_recorded_provenance_and_preserves_historical_absence` |
| Tariff application and recalibration | `tariff.extract_tariff` requires a fitted log-link GLM; `apply_tariff` rejects unseen categories/nonfinite numerics; export recalibration checks aggregate amounts and row exposure floor. M50 restricts export to representable preprocessing and atomically replaces completed workbooks. | Zero observed total permits a zero recalibrated base. Library callers choose calibration data; CLI uses training positions. Generic transforms remain available to distillation but are rejected by export. M49 did not establish export fidelity or failure safety; M50 adds that evidence. | `tests/test_tariff.py::test_exported_intervals_independently_reproduce_boundary_premiums`; `tests/test_tariff.py::test_apply_tariff_unknown_categorical_level_raises`; `tests/test_tariff.py::test_apply_tariff_rejects_nonfinite_numeric_input`; `tests/test_tariff.py::test_zero_total_recalibration_keeps_zero_rates`; `tests/test_tariff.py::test_export_supported_pipeline_has_independent_workbook_prices`; `tests/test_tariff.py::test_export_rejects_unsupported_preprocessing_before_writing`; `tests/test_tariff.py::test_export_failures_preserve_destination_and_remove_temporary_files`; `tests/test_tariff.py::test_distillation_preserves_generic_transforms_and_passthrough`; `tests/test_tutorial.py` |

#### Diagnostic-extension exercise: M49 baseline

M49 actually added and then discarded `predicted_claim_amount_test` in a disposable
copy of `src/azoic`, using the installed local environment and synthetic data only.
Definition: `sum(predicted_rate_test * exposure_test)`, aggregate currency on the
evaluated holdout, never a weighted mean or an observed amount. Two production
locations changed in that copy:

1. `workflow._evaluate_split`: add `float(np.dot(pred_test, exp_test))` to the
   `metrics` dictionary. Understand rate versus aggregate units, positional
   splits, optional training diagnostics and ordinary versus tuning evaluation.
   At M49 the function also constructed estimators/pipelines and assembled `Run`;
   trials called it with `diagnostics=False` and still built a `Run`. M53 separates
   these responsibilities as recorded in section 6.
2. `reporting._metrics_block_md`: add the label and display format. The card
   enumerates metrics; `comparison_table` expands `ModelResult.metrics`, and
   the dashboard's table uses those columns. Its three chosen charts stay explicit.

Trace, but do not change, `workflow.ModelResult.metrics` (`dict[str, float]`),
`Run.models`, `tune._make_objective` / `_objective_value` (the objective still uses
only deviance and O/P), final tuning assembly, `reporting.comparison_table` /
`comparison_dashboard`, and `mlops.log_run` (finite values get `<model>.<metric>`
keys). No config, root export, CLI, new result field or logging change is needed.
A test asserting the entire metric dictionary, such as
`test_run_records_exact_fit_and_holdout_positions`, needs an expected-key update
if an extension is retained. Reporting expectations and unit labels also need review.

Reproduction fixture: one constant predictor, periods 0–7, exposures
`[1, 2, 1, 2, 1, 2, 1, 2]`, amounts `[1, 6, 1, 6, 1, 6, 2, 8]` and counts
`[1, 2, 1, 2, 1, 2, 1, 2]`. Use a temporal 25% holdout and unpenalized Poisson
log-link GLM (`alpha=0`, `gradient_tol=1e-10`). Training totals are 21 currency /
9 years, giving rate 7/3; test positions `(6, 7)` have 3 years and observed amount
10. The extension must equal **7**, and O/P must equal **10/7**. Repeat with one
Optuna trial whose only choice is `alpha=0`.

Both ordinary and tuned results reproduced those independent totals through the
result, model card, comparison table/dashboard and real local SQLite MLflow
logging. Ordinary `Run` and `(Run, estimators)` interfaces also passed. The
source copy and SQLite store were deleted after execution; no exercise metric
ships. The execution record and check results are in `PROGRESS.md` under M49.

Maintenance questions for the later repeat: can a second maintainer find the
arithmetic owner, name the units, distinguish inner from outer metrics and list
all presentation consumers? M49 identified friction in mixed construction/scoring/
assembly responsibility and exact-dictionary tests, rather than the generic result
or logging containers. Record that maintainer's observations rather than claiming
maintainability from this single-agent exercise or passing tests.

## 4. Model API conventions

### Experiment input and per-model preprocessing

`run_experiment(config, *, df=None)` and `tune_experiment(config, *, df=None)`
accept an in-memory pandas portfolio. When `df` is omitted, load
`config.data_path`; the path remains required configuration metadata. Both routes
validate the portfolio and fingerprint the actual frame, preserving its row order
for recorded split positions without mutating the caller's data.

`ModelSpec.preprocess: bool = True` applies the experiment's configured binner
and grouper. Set `preprocess=False` on a top-level model to use raw features on
the same input/split, including during tuning. A frequency-severity model's
components share its top-level preprocessing decision. Explicit component flags
are rejected and omitted from serialized configs and effective component params.

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

### Experiment to production tariff (M56–M62)

User-approved roadmap, recorded 2026-10-25 against `bdce5a1`. Implement one
independently reviewable phase per session in the order below; do not reopen
M49–M55. Guided Python and YAML share the existing configuration and artifact
contracts. Keep flat modules, current dependencies and the default docs theme.

| Milestone / phase | Scope and acceptance |
| --- | --- |
| M56 / 1 (completed) | Reliable first journey: self-contained installed-package starter with explicit predictors, direct GLM, raw-feature GBM, understandable diagnostics and direct GLM export. Remove test-fixture/checkout/Quarto requirements from that journey. Distinguish released examples from checkout-only capabilities. Validate Python 3.12 on Linux and Windows; limit platform claims to observed evidence. Data errors identify columns, invalid-row counts and a bounded sample of row positions without weakening rules. Acceptance: fresh environments execute the documented journey without undocumented setup or repository imports. |
| M57 / 2 (completed locally) | Freeze a final-test portfolio and row membership before experimentation; existing experiment/tuning functions consume development data and label comparisons as development evidence. Require explicit predictors in the guided path, excluding identifiers, incumbent rates and partition metadata. Add a read-only config/data check using existing rules, with no dropping, repair or caps. Record exposure unit, currency, observation period, claim valuation basis and externally applied caps/adjustments. Acceptance: final-test outcome changes cannot alter development mappings, tuning, calibration or predictions; errors remain actionable. |
| M58 / 3 (pending) | Standard Python persistence for fitted candidates: run/config, preprocessing, estimators, versions, data identity and split membership together; training data excluded by default. CLI comparison/reporting/scoring/export accept saved runs without fitting; config commands remain explicitly training operations. Tuning saves selected config and fitted candidates. Trusted artifacts require a matching environment, not arbitrary cross-version portability. Acceptance: fresh-process prediction equality and proof saved-run comparison/export do not fit. |
| M59 / 4 (pending) | Fixed per-feature bin/group mappings through Python and YAML, preserving interval closure, typed categories and explicit missing/unseen destinations. Mapping edits create a new candidate and refit its downstream model. Factor replacements record original values and reasons; fitted/revised tariffs stay distinct. Export revised tariffs with preprocessing through the existing validated workbook writer. Recalibration derives from revised predictions on the declared training population and records one multiplier. Acceptance: revise an age boundary, refit, override a factor, review and export matching rates; failed revisions preserve the original candidate/workbook. |
| M60 / 5 (pending) | Tariff-review Markdown report plus complete CSV tables using existing plots. Align incumbent technical rates by unique record ID, rejecting missing/duplicate/mismatched membership. Compare incumbent/fitted/recalibrated/revised rates on identical observations with explicit scales. Include training O/P, validation metrics, portfolio/segment totals, exposure/available claims and temporal diagnostics; rate-change distribution, affected segments, mapping/factor changes, rationale and limitations. Zero incumbent rates have explicitly undefined percentage changes. Acceptance: a senior reviewer can explain changes, affected groups and selection without the notebook; no universal approval thresholds or unsupported superiority claims. |
| M61 / 6 (pending) | Evaluate a frozen fit on supplied final-test data without fitting/recalibration. Separate explicit production refit freezes selected features/settings/approved mappings and fits parameters on the declared full portfolio, then reapplies recorded overrides and calibration policy. Keep a new artifact and comparison to its evaluated predecessor; holdout results stay with that earlier fit. Deliver the three-sheet workbook, versioned specification, fitted Python artifact, batch-scoring recipe and synthetic cases with expected unrounded rates. Specify feature types/units/mappings/closure/missing/unseen behavior/calibration/artifact identity and evaluation/refit evidence. Acceptance: Python scoring works and a receiving engine has unambiguous agreement cases; release/deployment/rollback ownership remains downstream. |
| M62 / 7 (pending) | Measure roughly one million rows and tens of variables on declared hardware with thread settings, per-stage loading/preprocessing/fitting/diagnostic time and peak memory. Quantify avoided fitting first; cache transformations only if measured dominant and only for an identical training partition/configuration. Observe at least two medior actuaries, one senior and one ML engineer unaided; record failures, help, time and misunderstandings, then fix blockers. Acceptance: personas complete their handoffs unaided; speed claims reflect measurements, with no advance runtime promise. |

M57 implementation uses `data.split_portfolio` with predeclared final-test IDs
and separately saved portfolio/membership files. `DatasetSpec.id_col` and
`excluded_cols` exclude non-predictors; basis fields only record upstream
assumptions. `workflow.check_experiment` and `azoic check` are read-only and
require explicit predictors. Existing workflow/tuning take development frames;
`Run.record_ids` aligns with positional training/validation membership. Comparison
tables add a development-evidence column, requiring a minor release under the
public schema policy. Persistence/final evaluation remain M58/M61 work.

Every phase retains existing gates and adds focused behavioral checks. Cover
Python/YAML equivalence; ordinary/tuned artifact prediction and mapping fidelity;
manual edits through refit/export; candidate-specific training calibration;
matching report populations and reconciled totals; failed-write preservation;
and refit labels that cannot inherit independent holdout claims. Quote cases
cover exact/neighboring boundaries, missing/unknown inputs, typed levels and
rate versus period-cost units. Update exports, typing, examples, CLI help,
compatibility notes and project records with each interface change; apply the
minor-release policy to breaks.

This remains technical pure premium. Commercial loadings, taxes, discounts,
retention, claims development and inflation assumptions stay explicit upstream
or downstream choices. Defer a graphical workbench, generic deployment system,
new model families, standalone workbook scorer and distributed execution.
M56 records observed Linux/Windows starter execution. Independent user sessions,
million-row benchmarks and a real receiving engine remain pending evidence,
not inferred from engineering tests.

### Engineering depth and maintainability (M49–M55)

The user-approved replacement plan runs one phase per implementation session in
this order. Keep the flat architecture; no runtime dependency, validation
framework, orchestration class or speculative upper bound is required.

| Milestone / phase | Scope and acceptance |
| --- | --- |
| M49 / 1 (completed locally) | Current rule ownership, units, exceptions and independent runnable checks; perform/discard the diagnostic-extension exercise and record its change path. |
| M50 / 2 (completed locally) | Faithful export of Azoic bins/groups, workflow column removal and passthrough; reject unsupported preprocessing before opening destinations. Preserve generic distillation transforms. Atomic sibling-workbook replacement preserving existing permission bits; independent workbook arithmetic and serialization/save/permission failure preservation. Document newly rejected pipelines. |
| M51 / 3 (completed locally) | Verified `glum>=3.4.1`, `typer>=0.27.1` floors; retain locked Python 3.12 full suite, reuse wheel/sdist model/preprocessing/all-five-CLI smokes for low-version Python 3.12 metadata installs and Python 3.14 wheels; distinguish tested stacks from Python metadata support. Low-version installs read direct requirements from wheel metadata and use `lowest-direct` with current transitive versions; Python 3.14 uses current compatible wheels. Both resolve without the checkout lock, check installed dependencies and record exact versions. |
| M52 / 4 (completed locally) | Private shared outcome validator in `data.py` used by workflow/FSM: aligned finite vectors, row exposure floor, non-negative amounts/counts, optional count/amount consistency. Keep schema, supplied-rate, severity, explicit-weight and segment policies at their boundaries; calibration counts must be aligned 1D vectors, including valid `[3, 4]` summing to seven. |
| M53 / 5 (completed locally) | Separate estimator/input construction, fixed-shape split results and final `Run` assembly within current modules; trials consume scores without final-run assembly, training diagnostics or provenance. Share fixed-power scoring with stability while retaining warning/rejection differences; replace private-patching tests with behavioral checks and preserve all public results/splits/mappings. |
| M54 / 6 (completed locally) | Static root re-exports with lazy runtime imports; concrete public annotations, `Self` and `return_estimators` overloads. Document justified heterogeneous/third-party `Any` boundaries. Move RiskGBM validation to fit, including after `set_params`; update callers and exception-timing migration notes. Publish the composition contract and Azoic 0.x policy below; remove annotation-only workflow imports from reporting/logging through the lazy root. Verify downstream typing, import identities, cloning, pipelines, estimator checks, targeted FSM CV and installed wheel/sdist composition. |
| M55 / 7 (completed locally; independent validation pending) | Snapshot actual full constructor settings in defaulted `ModelResult.resolved_params`, qualified classes/sklearn component paths; record final-run `runtime_versions` and effective `tuning_settings`, including sampler/seeds. Deep-copy containers, preserve config/params, collect metadata once per final run, expose compact cards/separate MLflow prefixes; historical provenance stays explicitly unrecorded. Repeat the M49 diagnostic exercise and obtain independent maintainer observations for M54's documented component exercise, or explicitly leave that validation pending. |

Public API breaks are permitted when justified, with callers/tests/docs/project
rules and migration notes updated together; no test-only private compatibility
aliases. Experiment/tuning return interfaces stay intact; new provenance fields
have defaults for manually constructed results. Reproducibility here means audit
provenance: callers retain responsibility for data, environments and fitted models.
Focused checks and `just check` apply to every phase, strict docs to documentation/
interface changes. Later verification includes ordinary/tuned runs, claim-free
holdouts, missing routing, mapping overrides, upstream contracts and installed
packages. Release publication, portable replay, licensing provenance review and
independent maintainer validation are separate pending work. No later phase is
started by completing M49.

M53 keeps `_build_model` responsible for the estimator/pipeline and required
input columns, `_evaluate_split` responsible for fixed-shape internal results,
and `_assemble_run` responsible for public snapshots and fingerprinting. Trial
objectives use internal metrics directly; only the final outer refit builds
`ModelResult`/`Run`, training diagnostics and provenance. Shared
`metrics._tweedie_scores` computes fixed-power rate deviance and partition-relative
D²; workflow retains warning plus inf/NaN for nonpositive predictions, while
stability retains strict rejection. Public result fields, split positions,
preprocessing mappings and return interfaces are unchanged.

#### M54 extension boundary — implemented locally

The public contract and executable component recipe are published in
[`docs/reference/compatibility.md`](docs/reference/compatibility.md). M54's
acceptance and exact tested stacks are recorded in `PROGRESS.md`; M55 adds
final-run provenance separately. Independent maintainer evidence remains pending.

Support Python component composition without expanding workflow construction,
serialization or tuning: keep `ModelSpec.kind` unchanged. Keep `Run` and
`ModelResult` in `workflow.py`, including the concrete, runtime-validated
`Run.config: ExperimentConfig`. Extraction is deferred until a concrete consumer
needs results independently of workflow configuration. Do not publish
`azoic.testing.check_estimator`; reconsider only if adopters repeatedly need the
same narrowly defined Azoic-specific checks.

Preserve the existing root `__all__` inventory and documented defining-module
imports. Root and workflow `Run` / `ModelResult` must remain identical classes.
Reporting/logging should use `import azoic` and `run: azoic.Run` with postponed
annotations: fresh-process imports must avoid workflow, glum and LightGBM, while
`get_type_hints()` must still resolve the same `Run` on demand. Type-only imports
alone are insufficient for runtime annotation inspection. Result validation,
container mutability and experiment/tuning return interfaces must remain intact.

The published compatibility scope will cover declared exports and explicitly
documented constructors, methods and attributes; incidental imports and
undocumented implementation state gain no promise. During `0.y.z`, patches
preserve this documented contract; justified incompatible changes require a
minor release and migration notes, without a mandatory warning period. This is
an Azoic policy, stronger than [SemVer's 0.x baseline](https://semver.org/spec/v2.0.0.html#spec-item-4).
It must not freeze defects scheduled for M50–M55 or turn M49 observations into
permanent guarantees.

Document the following supported component and state boundaries:

- `FrequencySeverityModel(freq=..., sev=...)` components support sklearn cloning,
  parameter inspection and nested `get_params` / `set_params`. They accept
  `fit(X, y, sample_weight=...)` directly, return themselves, accept the supplied
  feature DataFrame and categorical representation, and predict one finite value
  per row. No Azoic inheritance or component `score` method is required.
- Frequency predictions are claims per exposure unit; severity predictions are
  currency per claim. FSM clones prototypes (which remain unfitted), removes
  special columns, uses count/exposure with exposure weights for frequency, and
  fits positive-count rows with amount/count and claim-count weights for severity.
- Azoic regressors cover documented constructor parameters, `fit`, `predict`,
  `score`, `get_params`, `set_params` and sklearn protocol behavior. Documented
  fitted state covers feature metadata, GLM `backend_` / `coef_` / `intercept_`,
  GBM `backend_`, and FSM `freq_` / `sev_`. Backend access does not extend Azoic's
  compatibility promise to third-party internals.
- Preprocessing covers documented fitting, transformation, feature-name and
  mapping APIs, including fitted mappings and missing destinations. `Run` covers
  `config`, `data_fingerprint`, row counts, split indices, `feature_names` and
  `models`, `runtime_versions`, `tuning_settings`; `ModelResult` covers `kind`,
  `params`, `resolved_params`, `metrics`, `calibration_table`
  and `protected_calibration`. Frozen attributes do not imply deep immutability
  of their public dictionaries, lists or DataFrames.
- No Azoic-specific subclass override hooks or internal call order are promised:
  `_make_backend`, `_pop_weight`, `_strip_specials` and orchestration helpers stay
  internal. Subclass authors maintain the public estimator contract; refer to
  sklearn's estimator protocol rather than instructing everyone to subclass Azoic.
- Portfolio/configured exposure keeps its one-day floor. Explicit model weights
  stay aligned, finite, non-negative and positive in total; individual zero and
  sub-day-sized weights remain legal. Severity count weights, ranking weights
  and diagnostic segment totals retain their separate policies.

The bounded conformance recipe uses mean `DummyRegressor` components and a
constant feature, with exposure `[1, 3, 2]`, count `[1, 2, 0]` and amount
`[10, 60, 0]`. Independent frequency is `3/6 = 0.5`; severity is `70/3` from
targets `[10, 30]` weighted `[1, 2]`; pure premium is `35/3`; predicted aggregate
amount is 70 and O/P is 1. Test-only recorders verify received targets, weights
and feature columns. Assert prediction shape, unchanged caller inputs, unfitted
prototypes, prediction without specials, cloning, nested parameters and an outer
sklearn pipeline. Two-fold CV uses two copies of the fixture so each training
fold contains severity observations; it tests integration, not generalization.

Require broken variants to fail the intended assertions: ignoring frequency
weights gives `350/27`, ignoring severity weights gives 10, aggregate severity
gives 35, a component column-vector prediction produces an invalid `(3, 3)`
product, and missing cloning support prevents construction/fitting. Existing
explicit-weight regression must detect an incorrectly imposed exposure floor.
These are requirements on the test exercise; current FSM does not validate
component prediction shapes at runtime. Aggregate balance is an oracle for this
mean predictor only, not a universal GLM/GBM/regularization requirement.

Document upstream `check_estimator` alongside the recipe; retain Azoic's explicit
strict-1D-target expected failure and do not suppress unrelated failures. Passing
checks establish only the tested conventions/integration, not statistical validity,
calibration, absence of leakage or correct business units in arbitrary components.
Acceptance includes focused tests, `just check`, strict docs, downstream typing
and the runtime-only consumer outside the checkout against both wheel and sdist,
using public imports. Extend the existing distribution smoke; report the tested
dependency stacks without claiming every metadata-permitted combination works.

#### M55 diagnostic repeat complete; independent validation pending

M55 repeated and discarded M49's diagnostic after the refactoring. Ordinary/tuned
results, cards, comparison tables/dashboard tables and real local SQLite MLflow
preserved independent predicted amount 7 and O/P `10/7`. Only the metric entry in
`workflow._evaluate_split` and its card label in `reporting._metrics_block_md`
needed changes in the disposable source copy; no exercise metric ships. Execution
and installed-artifact evidence are recorded in `PROGRESS.md`.

That single-agent repeat does not establish third-party compatibility, subclass
hooks or independent maintainability. An independent maintainer must
reproduce the installed-package component recipe from the documentation without
private imports or coaching and report ambiguities. No independent validation
has occurred; record unavailable observations as pending, never as acceptance.
Reconsider widening `kind` only for a concrete construction request covering
configuration, tuning and downstream consumers.


- **WP5 — ergonomics (P2) — completed 2026-10-23**: in-memory experiment/tuning input, predictor-only
  CLI profiling, per-model preprocessing, flattened MLflow preprocessing params,
  integer report labels, concise bin labels, and lazy public package exports.
  Tutorial compares a binned/grouped GLM with a raw GBM in one run. Existing
  `run_experiment(df=)`/CLI export reuse is retained and regression-covered.
  *Done when regressions, synthetic tutorial chapters, `just check`, and strict
  `just docs-build` pass. Earlier WP fixes and release publication are separate.*

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
  The site documents current behavior without a version-migration page.
  The 2026-10-16 release review found an existing GitHub `0.4.1` release but no
  visible PyPI project; see the current M15 scope below.
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
- **M15 — first PyPI release (completed 2026-10-17)**: published `0.5.0` /
  `v0.5.0` at commit `8a21acc` through release PR #2 and the existing OIDC
  workflow. The historical GitHub `0.4.1` release failed to publish because its
  publisher was not configured; its tag is preserved. The new release covers
  the full corrected delta through M45. Release tags must equal `v` plus the
  package version; installed artifact smokes cover preprocessing contracts and
  every CLI command. Registry installation is documented alongside the checkout
  route. Full scope/history: [the recorded plan](PREPROCESSING_FIX_PLAN.md).
  *Done when PyPI exposes the release, a fresh isolated install reports the
  finalized version and all five CLI commands, installed preprocessing
  regressions pass, and release/documentation workflows are green.*
  Codex review, PR/merge CI, full Quarto/Pages, and release build/publish passed.
  Published hashes and provenance match the workflow artifacts; a fresh Python
  3.12 registry install, 64 M45 cases, first model, and all five CLI commands
  passed. See `PROGRESS.md` for the completion checkpoint.

- **M16 — preserve the experiment holdout** — **completed 2026-09-05**:
  immutable `Run.train_indices` and `Run.test_indices` record actual fit and
  evaluation positions. Tutorial diagnostics, training calibration, and CLI
  distillation reuse them; CLI export loads the input frame once and fits only
  the requested model.
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

### M45 — preprocessing correctness (completed 2026-10-17)

Review confirmed three bugs: nonfinite `target_col` outcomes bypass validation
(and numeric-string `y` can become nonfinite after conversion), zero-weight
empty bins crash monotonic pooling on tied/constant predictors, and switching
between named DataFrames and arrays can silently skip fitted transformations.
The experiment workflow separately validates portfolio outcomes.

Delivery order remains **M45 → M15**, one milestone per session. Both transformers
now reject nonfinite supplied outcomes before learning while preserving
rate/aggregate units, optional target fallback, and missing predictors.
Monotonic pooling uses occupied bins with original upper edge positions;
constant predictors yield one observed-value interval. Transform input that
cannot match fitted mapping columns raises clearly; intentional passthrough
behavior remains. Added focused regressions and updated preprocessing contracts
without a new dependency or framework.

Acceptance: demonstrate the regressions before fixing; pass focused preprocessing
tests, `just check` (including workflow/tutorial/tariff checks), strict docs, and
diff/link checks. Use one focused fix PR with three topical commits; keep version
changes, publisher configuration, and publication in M15. Full scope, acceptance,
PR delivery, and release management are in
[PREPROCESSING_FIX_PLAN.md](PREPROCESSING_FIX_PLAN.md); execution checkpoints
remain in [PROGRESS.md](PROGRESS.md#preprocessing-correctness-and-release-plan--2026-10-16).

Local acceptance passed on 2026-10-17: 64 new cases, full preprocessing tests,
Ruff/Ty, **1119 tests** (4 skips, 2 expected failures), strict docs, rendered
contracts, local references, and formatting/diff checks. M45 merged in
[PR #1](https://github.com/ThomasBury/azoic/pull/1) after Codex review and green
CI. M15 subsequently published `0.5.0` / `v0.5.0` after release PR #2 and all
release/post-publication checks passed.

### M46 — ARFS-style LightGBM preprocessing (completed 2026-10-23)

Adopt one LightGBM regression tree per feature without adding ARFS as a dependency.
`AutoBinner` defaults to `tree`; `AutoGrouper.similarity` uses native categorical
splits for nominal levels and numeric codes for ordered contiguous groups.
Targets remain rates weighted by exposure, with special columns inside X.
Collapse sibling subtrees for either exposure/claim-count floor, keeping one group
when portfolio floors are impossible. Numeric monotonic pooling uses observed
weighted means and preserves floors. Retain quantile/rare alternatives.

Transform through native leaf predictions and frozen leaf-to-group maps. Keep
inspectable mappings, stable vocabularies, schema/index/column preservation and
serialization. Changed tree mappings need explicit keyword-only missing routes;
unchanged round-trips preserve native routing. Learned tree edges use `<=`;
quantile/manual numeric edges stay lower-inclusive. Export closures and missing
routes; keep strict tariff application. Validate 1D targets, finite controls,
monotonic options unconditionally, and fitted feature names.

Acceptance: focused partition/routing/floor/override regressions, sklearn checks,
pipeline and tariff agreement, serialization, `just check`, strict docs, installed
wheel/sdist and synthetic tutorial smokes. No release, ARFS dependency, real-data
performance claim, or automatic next milestone. Old fitted preprocessors need
refitting; predictive improvement remains to be demonstrated.

Local acceptance passed: **1239 tests**, 4 skips and 2 expected failures, Ruff/Ty,
strict docs, six isolated synthetic tutorial chapters within the 12 tutorial
checks, workbook boundary/prediction agreement, and installed wheel/sdist smokes.
Execution evidence and the uncommitted branch handoff are in `PROGRESS.md`.

### M47 — source-to-target evidence (completed 2026-10-23)

Extend the portfolio chapter with an independent mapping/`math.fsum` reference
from pinned OpenML 41214/41215 version 1, verifying source checksums, claim-level
conservation, sequential policy exclusions, retained targets and final sampling.
Report missing severity coverage and count discrepancies without inferring their
causes. Define the capped observed rate and its selected population; register
known definitions and unresolved coverage, valuation, maturity and quotation-time
availability. Preserve loader rules, caches, claim counts and public interfaces.

Acceptance: network-free synthetic chapter-cell regressions, exact counts,
EUR 0.01 / 1e-8 policy-year tolerances, pinned source snapshot reproduction,
`just check`, strict docs, and isolated cached-source portfolio rendering.
Professional review is pending. This establishes accounting, not full-population
adequacy, ultimate costs, future performance or M46 superiority. Stop before
comparisons, Git delivery or release.

Local acceptance passed: **1252 tests**, 4 skips and 2 expected failures, Ruff/Ty,
strict docs, and the isolated cached-source portfolio render. Both source MD5s,
exact record/reported-count totals, exposure and monetary conservation, retained
targets and final sampling passed. Execution evidence and unresolved source
questions are recorded in `PROGRESS.md`; professional review remains pending.

### M48 — selection and target sensitivity (completed 2026-10-23)

Extend the portfolio chapter's pinned-source evidence study without changing
loader rules, public interfaces, architecture or dependencies. Compare policies
passing all rules except count/amount consistency with final retained policies,
before sampling: counts, exposure, reported frequency and severity-record coverage.
Describe absent severity shares by Area and fixed driver-age bands 18–24, 25–64,
65–100. Compare individual EUR 50k, 100k, 200k and uncapped recorded costs on the
same retained IDs. Show explicitly hypothetical missing-cost means at 0.5, 1 and
2 times retained mean capped severity-record cost, using the wider cohort exposure;
never treat those assumptions as recovered observations or change model inputs.
Correct the ingestion/preprocessing explanation and distinguish observed capped
rates from ultimate pricing costs. Professional review and predictive comparisons
remain pending; unidentified missing-cost effects do not block completion.

Acceptance: reproduce cohort counts and aggregate rates from checksummed original
records; exposure residuals within 1e-8 policy-years and monetary differences within
EUR 0.01; focused network-free cohort/stratum/scenario checks reusing reconciliation;
`just check`, strict docs and isolated portfolio rendering. Stop after M48.

Local acceptance passed: **1256 tests**, 4 skips and 2 expected failures, Ruff/Ty,
strict docs and final isolated rendering with source MD5/snapshot checks. Independent
reconstruction confirmed both cohorts, nine strata, four caps and three scenarios.
The wider cohort has 676,789 policies versus 667,673 retained; 9,116 absent-record
policies carry 9,657 reported claims. Fixed-ID recorded rates span EUR 131.35/year
(50k) to EUR 169.69/year (uncapped); hypothetical wider-cohort rates span EUR
163.02–238.66/year under the specified assumptions. Actual missing-cost effects
remain unidentified. HTML contents were checked; visual layout was unavailable
because local-file browser navigation is blocked. See `PROGRESS.md` for evidence
and the completed milestone handoff; no predictive superiority is claimed.

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
| Python >=3.12 metadata; explicit tested stacks | Locked Python 3.12 full acceptance; low-version Python 3.12 and current-wheel Python 3.14 installed-artifact smokes. Metadata does not establish all allowed combinations. |
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
