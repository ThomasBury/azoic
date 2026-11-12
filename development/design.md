# Design and maintenance contracts

This page owns durable architecture, invariants and deferred decisions. For current
status and unfinished acceptance, read [current work](README.md). For user-facing
API contracts and runnable component composition, use the
[compatibility reference](../docs/reference/compatibility.md),
[configuration/CLI reference](../docs/reference/configuration-cli.md) and task guides.
Historical plans/results live in the [archive](archive/PRD.md); they are not current instructions.

## Scope and architecture

Azoic models non-life technical pure premium, frequency and severity. Commercial
loadings, taxes, discounts, retention, claims development and inflation are explicit
upstream/downstream assumptions. It is not reserving, fraud detection, policy
administration, AutoML, a cloud platform or a Guidewire integration engine.

Keep 13 flat modules under `src/azoic/`, with no `utils.py` or speculative subpackages:

| Modules | Responsibility |
| --- | --- |
| `data.py` | Portfolio schema/loading, outcome validation, predeclared development/final membership |
| `profile.py`, `preprocessing.py` | Feature screening; native binning/grouping and fixed mappings |
| `models.py` | Explicit sklearn-compatible GLM, GBM and frequency–severity wrappers |
| `metrics.py`, `validation.py`, `plots.py` | Diagnostic arithmetic, splits and static plotting |
| `workflow.py` | Config, estimator construction, split evaluation, final result assembly, persistence, revisions and evaluation/refit |
| `tariff.py` | Distillation, tariff scoring/revisions, workbook export and production bundles |
| `reporting.py` | Cards, comparison/dashboard and full tariff-review evidence |
| `mlops.py`, `tune.py`, `cli.py` | Lazy MLflow, lazy Optuna and Typer entry points |

Use functions and sklearn composition rather than additional orchestration classes.
Keep pandas at boundaries and NumPy inside. GLM/GBM are core; heavy integrations
stay optional and lazy. `pyproject.toml` owns dependency floors/groups/extras;
`uv.lock` and `.python-version` own the locked contributor environment. Metadata
support is broader than observed test stacks; do not imply every allowed stack works.

## Rule ownership and runnable evidence

Amounts are aggregate currency, exposure is policy-years and predictions are
currency per policy-year unless stated otherwise. `data.py` owns `MIN_EXPOSURE`
and `EXPOSURE_FLOOR` (one day with 0.1% tolerance). Keep portfolio row exposure,
explicit model weights, ranking weights and diagnostic segment totals as distinct
policies. Schema-only validation does not validate outcomes. Evidence paths below
are repository-root pytest nodes; run them with `uv run pytest NODE` after contributor setup.

| Rule and units | Current owner and enforcement boundaries | Deliberate exceptions or limits | Runnable evidence (pytest node) |
| --- | --- | --- | --- |
| Portfolio outcomes: finite, non-negative amounts/counts; row exposure at least one day; counts and amounts zero together | `data._validate_outcomes` validates aligned 1D vectors for `workflow._validate_portfolio` (ordinary/tuned entry) and `FrequencySeverityModel.fit` | `load_data` checks required columns only. Count/amount consistency applies when counts are configured. Schema, supplied-rate and severity checks stay at their boundaries. | `tests/test_workflow.py::test_run_experiment_rejects_inconsistent_claim_rows`; `tests/test_models.py::test_freq_severity_rejects_invalid_outcomes_before_components` |
| Exposure versus explicit model weights | `models._pop_weight` strips configured exposure; validates aligned, finite, non-negative, nonzero-total weights in fit/score; applies row floor to popped exposure | Explicit `sample_weight` overrides the column and has no day floor; zero entries are legal with positive total. Prediction can omit exposure. | `tests/test_models.py::test_explicit_sample_weight_is_not_floored`; `tests/test_models.py::test_m34_scoring_weight_contract`; `tests/test_models.py::test_popped_exposure_below_one_day_raises` |
| Pure-premium rate targets and scores | Workflow divides amount by exposure; model `_validate_target` checks finite, aligned 1D targets; FSM checks supplied rate equals amount/exposure | Aggregated amounts belong in diagnostic inputs, not estimator targets. Direct wrapper target support also depends on backend family. | `tests/test_workflow.py::test_run_records_exact_fit_and_holdout_positions`; `tests/test_models.py::test_freq_severity_fit_rejects_aggregate_or_mismatched_target`; `tests/test_models.py::test_m34_invalid_targets_rejected_before_backend` |
| Frequency (claims/year), severity (currency/claim), product (currency/year) | `FrequencySeverityModel.fit` clones components; frequency uses count/exposure weighted by exposure; severity filters positive-count rows and uses amount/count weighted by count | Severity claim-count weights are explicit weights, never exposure. Claim-free training cannot fit severity; claim-free holdouts remain evaluable. | `tests/test_models.py::test_freq_severity_severity_fit_is_filtered`; `tests/test_models.py::test_freq_severity_rejects_portfolio_without_severity_observations`; `tests/test_tune.py::test_tuning_completes_with_claim_free_inner_and_outer_holdouts` |
| Feature schema and exclusion of outcomes, times and protected columns | `DatasetSpec`, `ExperimentConfig.feature_columns`, workflow column selection/drop; model `_store_fit_meta` / `_check_model_features`; preprocessing `_validate_transform_input` | Standalone GLM/GBM only strip configured exposure. Other outcome columns must be removed by callers. Optional specials may be absent at prediction; predictor names/order must match. | `tests/test_models.py::test_m34_model_predictor_schema`; `tests/test_workflow.py::test_protected_audits_use_outer_test_and_never_fit_columns`; `tests/test_preprocessing.py::test_preprocessing_transform_tolerates_absent_special_columns` |
| Supervised preprocessing outcomes and credibility floors | `preprocessing._column_array`, `_resolve_target`, `_check_controls`, `_fit_tree`; configured amount/exposure becomes a rate; counts constrain credibility, never learning weights | Explicit `y` fallback is already a rate. Tree/similarity need outcomes; quantile/rare remain alternatives. Preprocessing exposure has a row floor, unlike grouped diagnostics. | `tests/test_preprocessing.py::test_preprocessing_preserves_target_fallback_and_exposure_units`; `tests/test_preprocessing.py::test_weighted_numeric_tree_matches_replicated_exposure`; `tests/test_preprocessing.py::test_weighted_native_partitions_match_replicated_exposure` |
| Missing predictors and mapping interpretation | GBM routes missing values natively; binner/grouper store `mapping_`, `missing_`, `closure_` and categorical vocabulary; mapping overrides validate before committing state | Tree intervals use upper-inclusive `<=`; quantile/manual intervals are lower-inclusive. Changed native mappings require an explicit missing destination. Grouper unseen levels route with missing levels; GLM has no native missing routing. | `tests/test_models.py::test_m34_gbm_keeps_native_missing_features`; `tests/test_preprocessing.py::test_native_numeric_thresholds_and_roundtrip_use_less_equal`; `tests/test_preprocessing.py::test_changed_native_mapping_requires_explicit_missing_transactionally`; `tests/test_preprocessing.py::test_native_categorical_missing_unseen_and_frozen_vocabulary` |
| Fitted state, cloning and parameter validation | Models guard `backend_` / `freq_`; transformers guard `mapping_`; sklearn cloning and fitted metadata remain module responsibilities | Constructors store controls unchanged; fit validates power/constraints, including after `set_params`. Backend internals and private override hooks carry no compatibility promise. | `tests/test_models.py::test_sklearn_compatible`; `tests/test_preprocessing.py::test_sklearn_compatible`; `tests/test_models.py::test_riskgbm_invalid_power_at_fit_after_set_params` |
| Ranking versus calibration | `metrics._as_arrays` validates diagnostic vectors; `_concentration_curve` integrates tied predicted scores; `op_ratio` compares sum(amount) with sum(rate × exposure) | Ranking accepts zero/sub-day weights and returns zero Gini for zero total claims/exposure. Positive prediction scaling preserves ranking but changes O/P. | `tests/test_metrics.py::test_tied_score_gini_has_hand_calculated_area_and_separate_calibration`; `tests/test_metrics.py::test_gini_zero_total_claims_or_exposure` |
| Grouped diagnostic exposure (years) and count totals | `calibration_table`, `one_way_table`, `double_lift_table` floor each segment's total exposure | Zero/sub-day rows can contribute to a valid segment. `stability_table` instead enforces the row floor. Optional calibration counts must be aligned finite, non-negative 1D vectors; they do not impose portfolio count/amount consistency. `[3, 4]` in one segment sums to seven. | `tests/test_metrics.py::test_grouped_diagnostics_floor_segment_totals_instead_of_rows`; `tests/test_metrics.py::test_calibration_table_rejects_zero_exposure_segments`; `tests/test_metrics.py::test_calibration_counts_reject_broadcasting_and_invalid_vectors`; `tests/test_metrics.py::test_calibration_counts_are_positional_segment_totals`; `tests/test_metrics.py::test_stability_table_rejects_sub_day_exposure` |
| Deviance and D²: weighted rates, fixed power 1.5 for experiment/stability comparisons | Shared `metrics._tweedie_scores` for workflow `_evaluate_split` and `metrics.stability_table`; deviance functions are upstream sklearn re-exports | Estimator scores use their family/objective power. Workflow warns and yields inf/NaN for nonpositive predictions; stability rejects them. D² uses the evaluated period's observed-mean null; zero null deviance gives NaN. | `tests/test_metrics.py::test_deviances_reexported`; `tests/test_workflow.py::test_run_deviance_is_exposure_weighted_tweedie_power_1_5`; `tests/test_workflow.py::test_temporal_test_d2_matches_period_baseline`; `tests/test_workflow.py::test_run_experiment_handles_clipped_zero_predictions_and_ordered_protected_cols` |
| Evaluation boundaries and holdout membership | `validation.temporal_split` keeps equal timestamps together; workflow records positional splits; tuning derives inner splits only from outer training and evaluates final models on outer test | Protected diagnostics are descriptive outer-test evidence. Comparison warns on incompatible data/target/exposure/holdout contexts. Distillation callers must supply disjoint observations; object identity cannot establish independence. | `tests/test_validation.py::test_temporal_split_keeps_equal_timestamps_on_one_side`; `tests/test_validation.py::test_temporal_split_rejects_missing_times_and_empty_cutoff_partitions`; `tests/test_tune.py::test_tuning_does_not_inspect_outer_test_outcomes`; `tests/test_reporting.py::test_comparison_warns_once_for_mixed_evaluation_contexts` |
| Result snapshots and audit limits | Workflow `_assemble_run` deep-copies config and effective explicit params, fingerprints the canonical frame and records split positions once per final run; lazy package exports keep imports light | Frozen result attributes contain mutable public containers. Final assembly records full wrapper/preprocessing constructors, runtime versions and effective tuning once per final run; empty historical metadata stays unrecorded. This is audit evidence, not portable replay or backend fitted state. Caller owns data, environments and fitted-model storage. | `tests/test_workflow.py::test_run_snapshots_caller_configuration_and_nested_params`; `tests/test_workflow.py::test_data_fingerprint_covers_categorical_metadata`; `tests/test_init.py::test_package_exports_are_lazy_and_discoverable`; `tests/test_workflow.py::test_final_provenance_covers_defaults_components_and_independent_snapshots`; `tests/test_workflow.py::test_historical_results_keep_provenance_unrecorded`; `tests/test_tune.py::test_tuning_provenance_records_effective_controls_once_per_final_run`; `tests/test_reporting.py::test_model_card_has_compact_and_historical_provenance`; `tests/test_mlops.py::test_log_run_separates_recorded_provenance_and_preserves_historical_absence` |
| Tariff application and recalibration | `tariff.extract_tariff` requires a fitted log-link GLM; `apply_tariff` rejects unseen categories/nonfinite numerics; export recalibration checks aggregate amounts and row exposure floor. Export restricts export to representable preprocessing and atomically replaces completed workbooks. | Zero observed total permits a zero recalibrated base. Library callers choose calibration data; CLI uses training positions. Generic transforms remain available to distillation but are rejected by export. Export fidelity and failed-write preservation have independent regression coverage. | `tests/test_tariff.py::test_exported_intervals_independently_reproduce_boundary_premiums`; `tests/test_tariff.py::test_apply_tariff_unknown_categorical_level_raises`; `tests/test_tariff.py::test_apply_tariff_rejects_nonfinite_numeric_input`; `tests/test_tariff.py::test_zero_total_recalibration_keeps_zero_rates`; `tests/test_tariff.py::test_export_supported_pipeline_has_independent_workbook_prices`; `tests/test_tariff.py::test_export_rejects_unsupported_preprocessing_before_writing`; `tests/test_tariff.py::test_export_failures_preserve_destination_and_remove_temporary_files`; `tests/test_tariff.py::test_distillation_preserves_generic_transforms_and_passthrough`; `tests/test_tutorial.py` |

## Workflow and state boundaries

### Preprocessing and evaluation

- Native tree methods require outcomes and use native missing routing; quantile/rare
  remain explicit alternatives. Learned tree intervals are upper-inclusive (`<=`),
  manual/quantile intervals lower-inclusive. Changed native mappings require an
  explicit missing destination. Fixed numeric mappings declare edges/closure/missing
  bin; fixed groups use typed level/group records with explicit missing/unseen
  destinations. Unlisted features learn only on training rows; fixed settings survive
  Python/YAML refits. Preserve transaction-safe mapping validation.
- Save predeclared unique final-test IDs before experimentation with `split_portfolio`.
  Give workflow/tuning development data only: their `test` names mean development
  validation. `DatasetSpec.id_col`/`excluded_cols` never become predictors; basis
  fields record upstream assumptions. `check_experiment`/`azoic check` require
  explicit predictors and never fit or repair data. `Run.record_ids` aligns with
  split positions. Outcome errors show column names, counts and at most five
  zero-based positions, never row values or index labels.
- Keep estimator/input construction, fixed-shape split evaluation and final run
  assembly separate. Tuning trials consume split scores without public result
  snapshots, training diagnostics or provenance. Workflow/stability share fixed-power
  Tweedie arithmetic while retaining their warning versus rejection policies.

### Public results and provenance

- Keep static lazy exports, the documented root inventory and defining-module imports.
  Root/workflow `Run` and `ModelResult` are identical classes; retain concrete runtime
  `Run.config: ExperimentConfig`. Reporting/logging use postponed `azoic.Run`
  annotations so imports stay light and `get_type_hints` resolves on demand.
- Constructors store parameters unchanged; validate GBM power/constraints at fit,
  including after `set_params`. Preserve public sklearn component composition and
  its runtime-only distribution smoke. No private override hooks/backend internals
  gain a compatibility promise. Frozen attributes do not make containers deeply immutable.
- Final assembly snapshots full wrapper/preprocessing constructors with sklearn paths
  in `resolved_params`, runtime versions and effective tuning controls. Keep explicit
  config/params separate, deep-copy snapshots and leave historical metadata unrecorded;
  logging uses separate provenance prefixes. This is audit evidence, not portable replay.
- During 0.y.z, patches preserve the documented public contract; justified incompatible
  changes require a minor release and migration notes, without a mandatory warning
  period. Do not extract result classes, widen `ModelSpec.kind` or publish an
  Azoic estimator checker without a concrete consumer.

### Saved candidates and controlled revisions

- `save_run`/`load_run` persist the existing Run/fitted-estimator pair as trusted,
  same-environment protocol-5 pickle, excluding portfolio frames. Version checks
  occur after unpickling and are not a security boundary. Never load untrusted pickle.
- Keep saved report/compare/predict/export no-fit operations separate from config
  training. Saved GLM recalibration requires the original fingerprinted development
  frame and saved training positions; saved export cannot distill.
- `RevisedTariff` is a separate post-fit scoring artifact, not a model kind.
  `revise_run` preserves source state, verifies fingerprint/membership, refreshes
  development diagnostics and records factor reasons plus one training calibration
  multiplier. Export revisions with `recalibrate=False`; never recalibrate twice.

### Tariff review, final evaluation and production

- Workbook export supports native bins/groups, workflow column removal and passthrough.
  Reject unrepresentable transforms before opening workbooks. Generic distillation
  transforms remain supported. Preserve destination permission bits; replace only
  after fully saving a sibling temporary workbook. Retain the three-sheet contract.
- Tariff review scores frozen candidates on original fingerprinted development data,
  aligns incumbent technical rates by unique ID and rejects mixed basis/splits.
  Require a new output directory, complete CSV evidence and explicit candidate scales;
  percentage changes are undefined for every zero incumbent. Never fit/recalibrate
  while reporting. Selection and rationale are human declarations.
- `evaluate_final` evaluates the selected frozen fit without fitting/calibration.
  Require predeclared disjoint final membership and exact original full-portfolio
  identity. `refit_production` is separate: freeze native preprocessing, clone model
  parameters, reapply latest typed factor overrides and recompute the recorded
  calibration policy once on full rows. Production metrics are `_full` training
  evidence; predecessor final evidence remains attributed to the selected frozen fit.
- `export_production` creates a new versioned specification/workbook/trusted artifact/
  batch recipe/agreement bundle without fitting or recalibration. All model kinds
  can evaluate/refit; workbook delivery requires an exportable log-link GLM. Test
  exact/neighboring boundaries, missing/unseen rejection and rate versus period-cost
  units. Synthetic/Python agreement is not downstream engine or deployment evidence.

## Documentation, tutorial and packaged skills

- Public documentation is task-first: getting started, guides, reference and a bridge
  to the independent Quarto book. Keep Zensical's default theme, cards only on hubs,
  and JavaScript limited to the official MathJax helper/runtime. Internal maintenance
  records stay outside the published site. Do not commit generated outputs or fetched data.
- Each tutorial chapter creates its own artifacts; shared setup uses `include: false`.
  Direct GLM/raw GBM stay on the main path; explicitly construct the structured teacher
  in optional distillation/tuning. Show one numeric bin/group before full inspection,
  fold verification plumbing, retain assertions, label scales and figures with alt text,
  and mark deeper recipes optional. Synthetic assembly, sequential rendering and
  isolated rendering are separate checks.
- Tutorial source-to-target accounting preserves loader rules. Sensitivity uses the
  population passing all other rules, fixed Area/age strata and identical retained IDs
  across claim caps. Missing-cost scenarios are assumptions, never loader/model-input
  changes. Separate teacher fidelity from claims performance and label the 70% target
  loss-ratio premium example as an assumption. Workbook use still needs fitted
  preprocessing; do not introduce an Excel importer.
- Three user skills live in `src/azoic/.agents/skills/` as ordinary package data with
  self-contained references and minimal generated OpenAI metadata. Preserve automatic
  discovery and independent operation boundaries. Installation checks and version
  reconciliation are required by [agent instructions](../AGENTS.md#ci-and-delivery).
  Agent trials test only observed routing/actions, not universal host discovery or
  unaided practitioner acceptance.

## Deferred and demand-gated work

These are constraints, not scheduled milestones. Reconsider only with concrete need:

- Interactive individual diagnostics: real business exploration need beyond the existing
  Plotly comparison dashboard. Polars ingest: measured unacceptable pandas loading/RAM,
  converting at the boundary. No Polars/DuckDB core migration.
- Geo adjacency: a real constrained portfolio. Remote MLflow: a real endpoint.
  SageMaker: a named target environment. Guidewire: a concrete importer contract;
  the workbook already supports manual entry.
- Fused/group lasso: first test monotonic preprocessing and glum quadratic difference
  penalties on an unstable ordered factor. Residual modelling: require out-of-fold
  correction design and stable untouched-holdout improvement over direct GBM.
- Large-loss tails: claim-level severity plus a defined capping/censoring/excess-loading
  objective. ALE/SHAP/DALEX: optional only when PDP/ICE or native contributions do not suffice.
- Transformation caching: require measured dominant repeated work and an identical
  training partition/configuration; saved consumers already avoid relearning. The
  measured native lookup optimization adds neither caches nor new fitted state.
- Defer a graphical workbench, generic deployment system, new model families,
  standalone workbook scorer and distributed execution.

Earlier cuts remain deliberate:

| Cut/merged | Why | Replacement |
|---|---|---|
| 5 GLM estimator classes | class explosion | one `RiskGLM(family, link, exposure_col)` |
| 4 GBM estimator classes | class explosion | one `RiskGBM(objective, exposure_col)` |
| separate FreqSev wrappers per backend | needless duplication | one `FrequencySeverityModel(freq, sev)` (duck-typed) |
| `AutoTariffGLM` class | it's a Pipeline | construct `sklearn.pipeline.Pipeline` directly |
| 6 splitter classes | sklearn has it | `make_strata()` helper + sklearn splits; `temporal_split()` |
| custom deviance module | sklearn supplies it | re-export `sklearn.metrics.mean_*_deviance` |
| 5 clusterer classes | clustering = grouping | `AutoGrouper(strategy=...)`; geo adjacency only for a real constrained portfolio |
| 5 mlflow classes | thin shim is enough | `log_run()` function |
| `TariffOptimizer` constraint DSL strings | parser project | numeric penalties in optuna objective |
| 5 tariff exporter classes | one xlsx is the format | `export_tariff(glm, path)` |
| `TariffExperiment` sequencing class | functions compose | `run_experiment(config)` |
| `selection/` module (5 classes) | flags = profiler columns | `screen_features(profile)` |
| Hydra | one config, no composition yet | YAML + pydantic + Typer overrides |
| polars + duckdb in core | pandas is canonical | add Polars only for a measured ingest bottleneck; duckdb = notebook habit |
| plotly dual diagnostic backend | doubles test surface | existing Plotly comparison dashboard; add diagnostic charts only for a real business need |
| Textual, PowerPoint, ALE, geopandas | YAGNI for v1 | cut until concrete demand |
| `pydantic AND dataclasses` | overlap | pydantic only |
| `ModelCard.to_pdf` | windows weasyprint pain | Markdown-only `model_card()` |
