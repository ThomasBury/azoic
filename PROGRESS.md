# Azoic — Progress

> Living tracker. Mirrors `PRD.md` section 6 milestones. Update after every
> chunk of work.

Legend: ☐ pending · ◐ in progress · ☑ done

> Implement exactly one pending milestone per session. Mark it ◐ before implementation, run its acceptance checks, mark it ☑ only when green, then stop with a handoff. Do not start the next milestone automatically.

## Milestones

- ☑ **Tutorial age-chart presentation** — prioritize raw-value one-ways for
  both ages, retain fitted-group diagnostics, and replace the manual single-policy
  curve with a link to the existing sklearn PDP/ICE recipe. Separate exposure
  panels make sparse ages visible. Completed 2026-09-06: `just check` passed Ruff,
  Ty, and 678 tests (4 upstream skips); strict docs build passed; final `just demo`
  executed all 32 cells. Raw ages, shared comparison groups, and portfolio totals
  reconcile; frozen-mapping assertions pass. Visually checked the age figures and
  verified their exact PNGs are embedded in the rebuilt HTML. Generated outputs
  stay ignored. Handoff: presentation complete; M15 stays next.

- ☑ **Requested simplification cleanup** — remove the unused stratified split
  helper with migration guidance; simplify density plots, one-way labels,
  tuning results, and model-card rendering. Completed 2026-09-06: `just check`
  passed Ruff, Ty, and 678 tests (4 upstream skips); `just docs-build` passed
  strict mode; `just demo` executed all 32 cells and rebuilt the HTML. Numeric
  labels matched the previous implementation across 80 seeded cases. Generated
  outputs remain ignored. Handoff: requested cleanup complete; M15 stays next.

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
  comparison table; one-million-row bin merge reduced from 3.12s to 0.066s.
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
- ☑ **Documentation onboarding** — complete install and network-free first-model
  path; five focused guides; comprehensive configuration/CLI reference;
  top-level freMTPL2 tutorial; official MathJax integration; runnable checkout
  YAML.
- ☑ **M9 — contract and residual correctness (v0.4.1)** — standardize estimator
  and residual rate contracts; reconcile CLI/reporting documentation.
- ☑ **M10 — configuration-driven tuning** — typed optional trial settings and
  per-model parameter distributions with defaults preserved.
- ☑ **M11 — temporal stability diagnostics** — period-level exposure, totals,
  O/P, Gini, deviance, and \(D^2\) with full-input reconciliation.
- ☑ **M12 — protected-group audit** — prevent protected-column leakage and retain
  held-out subgroup calibration evidence.
- ☑ **M13 — interpretation recipes** — sklearn PDP/ICE and LightGBM native
  contribution examples without new wrappers or explanation dependencies.
- ☑ **M14 — documentation parity and release hardening** — document temporal
  stability, remove obsolete MLflow roadmap language, and validate wheel and
  source distributions before a least-privilege publish job.
- ☐ **M15 — first public release** — publish and verify `azoic==0.4.1` through
  GitHub Releases and PyPI trusted publishing, after M16–M23 are green.
- ☑ **M16 — preserve the experiment holdout** — immutable fit/test positions
  reused by tutorial diagnostics, training calibration, and CLI distillation.
- ☑ **M17 — reject inconsistent frequency-severity outcomes** — issue 2.
- ☑ **M18 — faithful tariff bins and similarity groups** — issues 3 and 4.
- ☑ **M19 — complete missing-value diagnostics** — issues 5 and 6.
- ☑ **M20 — valid diagnostic references and residual scales** — issues 7, 9, and 12.
- ☑ **M21 — correct actuarial explanations** — issues 8, 10, 11, and 13.

- ☑ **M22 — show what fitted preprocessing does**.
- ☑ **M23 — evaluate the exported tariff against claims**.

## Current focus

- M14 and M16–M21 are complete. The thirteen correctness findings supplied
  on 2026-09-05 are covered by the remediation evidence below. M22 and M23 are complete;
  milestone numbers retain their existing identity even though release comes last.
- **M16 and M17 are complete.** Frequency-severity fitting now validates all
  outcome rows before deriving rates or cloning/fitting either component.
  Direct, pipeline, and workflow rejection checks pass; evidence is below.
- **M18 is complete.** Tariff labels match boundary assignments, and nominal
  similarity grouping uses the closest adjacent aggregate risks. Boundary,
  grouping, full-suite, strict-docs, and fresh tutorial checks pass.
- **M19 is complete.** Weighted quantiles exclude missing rows and their
  exposure; one-way tables and plots retain the missing segment and its totals.
- **M20 is complete.** Claim-free holdouts report undefined D², the oracle
  ranks observed rates, and signed residual density remains visible on native
  symmetric log axes. Reporting, tuning, rendering, full-suite, and strict-docs
  checks pass; evidence is below.
- **M21 is complete.** Calibration factors use training rows for every tutorial
  candidate, raw/adjusted holdout metrics are labelled, and double-lift,
  residual, and Gini explanations have executable numerical evidence.
- **M22 is complete.** Fitted mapping tables, ordered GLM one-ways, and the
  frequency–severity appendix are verified below. The later presentation cleanup
  replaces the manual fixed-policy curve with raw-value one-ways for both ages.
- **M23 is complete.** The applied workbook is evaluated against held-out claims
  alongside the three main models, with separate raw/adjusted and fidelity evidence.
- Next implementation session: **M15 only** repeats distribution and isolated CLI
  checks before publication. This session stops at the M23 handoff.

## Correctness remediation plan — 2026-09-05

The reported baseline is **497 passed, 4 skipped**. Inspection of the current
code confirms the affected paths and reuse opportunities below. The supplied
numerical counterexamples are acceptance fixtures, not newly reproduced results
from this planning session. Passing the existing suite does not close these
findings. Preserve historical completed milestones and track corrections here.

Planning verification: `just check` passed Ruff, Ty, and **497 tests**, with
**4 skipped** (upstream array-API checks); `git diff --check` passed. Only
`PROGRESS.md` and `PRD.md` changed. No fixes are marked complete.

### Priority and delivery order

**P0** fixes invalid held-out evidence, silently excluded losses, or incorrect
tariff interpretation. **P1** fixes remaining model behaviour, diagnostics, and
actuarial explanations. Both priorities are prerequisites for M15. Related
changes share a milestone: issue 4 travels with tariff preprocessing and issue 6
with missing-value diagnostics.

| Priority | Issue | Consequence | Milestone |
|---|---|---|---|
| P0 | 1 — different split after fitting | Training policies appear in holdout charts and distillation validation | M16 |
| P0 | 2 — positive losses with zero count | Standalone fitting silently discards recorded losses | M17 |
| P0 | 3 — incorrect bin labels | Written tariff intervals can produce different premiums at boundaries | M18 |
| P0 | 5 — missing numeric rows omitted | One-way totals and calibration exclude losses and exposure | M19 |
| P1 | 4 — nominal similarity merges the risk tail | Different risks are pooled while similar risks stay separate | M18 |
| P1 | 6 — missing exposure enters quantiles | Missing observations change grouping of observed values | M19 |
| P1 | 9 — claim-free test period crashes | A valid experiment cannot report its remaining diagnostics | M20 |
| P1 | 7 — oracle ranks aggregate losses | The perfect-ranking reference is wrong when exposure varies | M20 |
| P1 | 12 — logarithmic signed residuals | Zero and overprediction errors disappear from view | M20 |
| P1 | 10 — GLM/GBM calibration claims | Model family is used to assume calibration instead of measuring it | M21 |
| P1 | 8 — double-lift interpretation | The narrative can recommend the worse model | M21 |
| P1 | 11 — residual calibration guidance | The suggested remedy confuses additive and multiplicative errors | M21 |
| P1 | 13 — Gini definitions conflated | Inequality, concentration, and signed area are taught as interchangeable | M21 |

Execute **M16 → M17 → M18 → M19 → M20 → M21 → M22 → M23 → M15**. M17 and M18 have
no code dependency on M16, but this sequence restores the evaluation boundary
first. Within M19, fix issue 6 before validating binned missing-value diagnostics.
M21 depends on M16 for calibration data and on M19/M20 for trustworthy plots.

### M16 — preserve the experiment holdout

**Issue 1.** The tutorial fits both runs through `run_experiment`, then calls
`stratified_random_split` independently. Equal seeds and lengths do not identify
the same rows. The supplied example has 159 training policies among 200 chart
test policies.

**Solution.** Record the actual positional `train_indices` and `test_indices`
as immutable integer tuples on the existing `Run`, populated in
`workflow._evaluate_split` from the arrays used to fit and evaluate. Keep the
current random/temporal split algorithms. The tutorial must take its partitions
from the returned run, assert exact equality between both runs, and reuse them
for every chart, training recalibration, and distillation fit/fidelity frame.
Retain the dataset fingerprint check and original row order: positions only
identify rows in that exact input frame. Remove the second split and its
stratification claims. Convert stored tuples to an integer array/list for
`DataFrame.iloc`, which interprets a bare tuple as multidimensional indexing.

Update the CLI distillation caller to use its returned run's positions too.
Tuning already routes through `_evaluate_split`: its final run must record the
outer partition, not an inner trial partition. Document the Run fields in the
existing workflow/configuration reference. No new splitter class, stratified
workflow option, or artifact store is needed.

**Acceptance.** In `tests/test_workflow.py`, use a synthetic portfolio and a
fit-recording estimator to check exact fitted membership against returned
positions for random and temporal splits. Assert disjointness, full coverage,
matching counts, and positional behaviour with a non-default index. Recomputed
*raw* holdout metrics must equal run metrics. Extend the existing outer-holdout
tuning and CLI distillation checks to verify row membership. Add tutorial
assertions that calibration/student fits use training positions and all
diagnostic/fidelity frames use test positions; lengths alone are insufficient.
Render the tutorial to exercise them. Label scaled predictions separately from
raw run metrics; M21 completes the calibration presentation.

**Completed 2026-09-05.** `Run.train_indices` and `Run.test_indices` now
capture the exact fitting/evaluation arrays as integer tuples. The tutorial
uses those positions for training adjustments, holdout charts, and student
fit/fidelity frames; it verifies both runs' partitions and reproduces their raw
holdout metrics and calibration tables before scaling predictions. CLI
distillation uses its returned run's positions and rejects a reloaded dataset
whose fingerprint changed. The workflow reference documents the fields,
positional indexing, and raw/adjusted distinction.

Acceptance evidence:

- Added/extended workflow, outer-tuning, and CLI checks first: **8 failed** on
  the missing positions or the unguarded changed dataset, as expected.
- `uv run pytest -q tests/test_workflow.py tests/test_tune.py tests/test_cli.py`:
  **94 passed**. Checks cover exact fitted membership with non-default indexes,
  random and temporal splits, immutable positions, coverage/disjointness, raw
  metric and calibration reproduction, final outer-tuning membership, and CLI
  use of the returned partition rather than reconstruction from its config.
- `uv sync --all-extras --all-groups --locked` succeeded; `just check` passed
  Ruff, Ty, and **502 tests**, with **4 upstream array-API skips**.
- `just docs-build` passed strict mode. `just demo` completed all **20 cells**
  on **667,673 policies** (**534,138 train / 133,535 test**), exercising the
  membership assertions, raw-metric equality, and student/workbook fidelity.
- `git diff --check` passed. Generated tutorial data, charts, HTML, workbooks,
  reports, and MLflow state remain ignored; no dependencies were added.

Handoff: M17 is next. The remaining grouping, missing-value, plotting, and
actuarial-explanation findings stay assigned to M18–M21; this render validates
M16's boundary correction, not release readiness.

### M17 — reject inconsistent frequency-severity outcomes

**Issue 2.** `FrequencySeverityModel.fit` selects severity rows with
`claim_count > 0` without checking the consistency already enforced by
`workflow._validate_portfolio`.

**Solution.** Apply the same outcome contract at the standalone estimator
boundary, before rate division, cloning, or fitting either component: exposure
must be positive and finite; counts and amounts non-negative and finite; count
and amount zero or positive together. Raise a clear `ValueError` for either
inconsistency. Keep supplied-rate validation and the internal positive-count
severity filter. Short local checks in `models.py` suffice; no validator
framework or dependency from models onto workflow is needed.

**Acceptance.** Extend `tests/test_models.py` with the 1,070-total-loss example:
the 1,000-loss/zero-count row must fail both with omitted `y` and with the correct
supplied rate. Verify the reverse inconsistency and invalid exposure/count/amount
values, with neither component fitted on rejection. Retain valid-data weighting,
outcome-free prediction, and no-valid-severity tests. Check direct estimator,
pipeline, and workflow paths against the same rule.

**Completed 2026-09-05.** `FrequencySeverityModel.fit` now rejects invalid
exposure, counts, amounts, and either count/amount inconsistency before rate
division, cloning, or component fitting. The supplied-rate check and internal
positive-count severity filter remain in place. Removed the zero-exposure
frequency fallback and unnecessary division-warning suppression. The estimator
docstring and model-choice guide describe the enforced contract.

Acceptance evidence:

- Added the regression cases first: **60 failed, 15 passed**. Standalone and
  pipeline paths lacked the outcome guard; the workflow already enforced it.
- The **75 rejection cases** cover the 1,070-total-loss example, its reverse
  inconsistency, zero/negative exposure, negative counts/amounts, and NaN/both
  infinities across direct, pipeline, and workflow paths. Direct and pipeline
  fits exercise both omitted and supplied rates. Clone/fit sentinels confirm
  that neither component is touched on rejection.
- `uv run pytest -q tests/test_models.py tests/test_workflow.py`: **272 passed,
  2 upstream array-API skips**. The extended existing fit spy verifies exact
  frequency/severity targets, exposure/count weights, filtered rows, and
  outcome-free prediction. Valid fits and no-valid-severity checks pass.
- `uv sync --all-extras --all-groups --locked` succeeded; `just check` passed
  Ruff, Ty, and **577 tests**, with **4 upstream array-API skips**.
- `just docs-build` passed strict mode. Ruff format checks and
  `git diff --check` passed. No dependencies were added.

Handoff: M18 is next. M18–M21 remain pending before M15; stop this session here.

### M18 — faithful tariff bins and similarity groups

**Issue 3 — interval contract.** Keep the existing `searchsorted(...,
side="right")` assignment used by fitting, bin merging, and transformation.
Correct `AutoBinner._labels` to express lower-inclusive, upper-exclusive bins:
`(-inf, 30.0)`, `[30.0, 60.0)`, `[60.0, inf)`. Preserve `Missing` and the no-edge
interval. This fixes the shared label source for category vocabularies, mapping
overrides, and tariff export without changing observation membership. Update
literal label expectations and document in the migration guide that existing
fitted artifacts/workbooks must be regenerated together: their categorical
vocabulary contains the old labels.

**Acceptance for 3.** In `tests/test_preprocessing.py`, check each edge and its
immediately adjacent floating-point values, multiple edges, missing values, and
`set_mapping` round trips. In `tests/test_tariff.py`, export a fitted pipeline
and independently apply the written interval inequalities and workbook factors
to raw boundary observations; premiums must match pipeline predictions with
recalibration disabled. Reusing the binner to assign verification rows would
hide the original defect.

**Issue 4 — nominal similarity.** Reuse the adjacent-risk merge logic in
`_ordered_similarity_mapping` for nominal levels after stably sorting their
statistics by aggregate pure premium. Keep declared category order for ordered
inputs. For the group limit, merge the adjacent pair with the smallest absolute
difference in `sum(claim_amount) / sum(exposure)`, recomputing aggregate risks
after each merge and breaking distance ties to the left. Apply the existing
nearest-neighbour credibility-floor handling as well. Remove the nominal
tail-merging loop; a narrowly renamed shared private method is sufficient.
Keep `rare` grouping and existing unknown-category behaviour. Update the
tutorial's trailing-group explanation and the preprocessing guide.

**Acceptance for 4.** Equal-credibility rates `100, 101, 10000` with
`max_groups=2` must pool the first two only. Add an unequal-exposure example
that distinguishes aggregate risk from an unweighted mean of category rates;
exercise recomputation, distance ties, and credibility floors. Preserve ordered
adjacency, mapping round trips, and sklearn checks in
`tests/test_preprocessing.py`. Correct grouping changes fitted models: refit and
regenerate evaluation evidence instead of retaining old metric claims.

**Completed 2026-09-05.** `AutoBinner` labels now describe the existing
lower-inclusive, upper-exclusive assignments without changing bin membership.
Nominal and ordered similarity grouping share `_adjacent_similarity_mapping`;
nominal statistics are stably sorted by aggregate risk first. Removed the
nominal tail-merging implementation. The preprocessing guide, estimator
reference text, and tutorial explain the corrected behaviour. The migration
guide requires refitting models and regenerating workbooks together because
labels are fitted category vocabulary and nominal groups can change predictions.

Acceptance evidence:

- Added counterexample checks before changing production code: **17 failed,
  8 passed**. Independently applying the old workbook inequalities selected
  different factors at both exact edges, 30 and 60.
- `uv run pytest -q tests/test_preprocessing.py tests/test_tariff.py`:
  **174 passed, 2 upstream array-API skips**. Checks cover one/multiple/no
  edges, adjacent floating-point values, missing values, mapping round trips,
  independent workbook premiums, nearest-risk merging, unequal-exposure
  aggregate risks, recomputation, stable sorting, left ties, exposure/claim
  floors, declared ordered adjacency, and sklearn conformance.
- `uv sync --all-extras --all-groups --locked` succeeded; `just check` passed
  Ruff, Ty, and **602 tests**, with **4 upstream array-API skips**.
- `just docs-build` passed strict mode; rendered guides show the corrected
  intervals and migration instructions. Ruff format and `git diff --check`
  passed. No dependencies were added.
- `just demo` completed all **20 cells** on **667,673 policies** (**534,138
  train / 133,535 test**). Models were refitted; raw holdout metric/partition
  assertions, regenerated charts/reports, workbook/student equivalence, and
  local MLflow artifact checks passed. The new tutorial, reports, and workbooks
  remain ignored.

Fresh raw held-out results for the affected tariff-structured models:

| Model | Gini | O/P | Tweedie deviance (power 1.5) |
|---|---:|---:|---:|
| Direct Tweedie GLM | 0.3098 | 1.0221 | 75.338331 |
| Frequency-severity GLM | 0.3136 | 1.0323 | 75.237864 |
| Tariff-structured Tweedie GBM | 0.3192 | 1.1236 | 75.285399 |

These refitted results supersede earlier tariff-structured evaluation evidence.
Handoff: M19 is next. M19–M21 remain pending before M15; stop this session here.

### M19 — complete missing-value diagnostics

**Issue 6 — observed-only quantiles.** In
`validation._weighted_quantile_edges`, exclude missing grouping values *and
their corresponding weights* before sorting, cumulative exposure, and edge
selection. Handle empty/all-missing input before indexing cumulative weights.
In `make_strata`, preserve `-1` for missing rows even when no edges remain;
observed rows may use the single group `0`. Preserve observed ties and the
existing no-positive-total-weight fallback. Reject non-finite/negative weights
and mismatched shapes; zero weights may retain their current meaning.

**Acceptance for 6.** In `tests/test_validation.py`, appending a missing row
with very large exposure must leave original observed boundaries/codes unchanged.
Cover all-missing input, one observed value, repeated values, zero usable weight,
and malformed weights. Exercise the shared callers: `AutoBinner`, calibration,
one-way, and double-lift tables. Their observed-only behaviour must remain stable.

**Issue 5 — retain the missing segment.** Use `dropna=False` in
`one_way_table` aggregation, as `calibration_table` already does. Give numeric
missing rows an explicit `Missing` display label in raw-value and binned modes,
including all-missing data; retain exposure, observed claims, and predicted
claims. Keep their numeric centre undefined rather than inventing a feature value.

Follow through to `plots.plot_one_way`: it uses numeric centres when *any*
centre is finite, which would still hide the retained missing segment. When a
numeric table includes missing centres, use the existing categorical positions
and labels for all groups, including the exposure panel/background. Complete
numeric tables retain their natural numeric axis.

**Acceptance for 5.** In `tests/test_metrics.py`, the three-policy example must
retain all 10,200 claims, with 10,000 in `Missing`; exposure and
`sum(prediction * exposure)` must also reconcile. Cover `n_bins=None`, the
low-cardinality numeric path, quantiled data, and all-missing input. In
`tests/test_plots.py`, check that the missing group's observed/predicted points,
label, and exposure have a finite display position in standalone and embedded
charts. A table-only fix is incomplete. Update the diagnostics guide.


**Completed 2026-09-05.** `_weighted_quantile_edges` now validates weights and
shapes before removing missing grouping values and their matching weights.
Empty/all-missing inputs return no edges; `make_strata` preserves missing code
`-1` even with no edges or zero usable weight. Observed ties and existing
zero-weight behaviour remain intact.

`one_way_table` retains missing numeric rows as `Missing` in raw-value and
binned modes, including all-missing features, with an undefined centre.
`plot_one_way` uses labelled positions whenever a centre is missing, including
for exposure bars. Complete numeric tables keep their natural numeric axis.
The diagnostics guide and API text document these contracts.

Acceptance evidence:

- Added counterexample checks before production changes: **37 failed,
  7 passed**, reproducing missing-weight boundary contamination, omitted
  claims/exposure, invalid-weight acceptance, and hidden plot points.
- `uv run pytest -q tests/test_validation.py tests/test_preprocessing.py
  tests/test_metrics.py tests/test_plots.py`: **269 passed, 2 upstream
  array-API skips**. Checks cover empty/all-missing/single/repeated values,
  zero usable weight, malformed weights/shapes, shared-caller invariance,
  raw/low-cardinality/binned reconciliation, nullable numerics, and finite
  missing-group points, labels, and exposure in standalone/embedded plots.
- The three-policy counterexample retains **10,200** observed claims,
  including **10,000** in `Missing`, with **8** exposure and **7,700** predicted
  claims. A further multi-bin check reconciles totals with large missing
  exposure while preserving the complete observed table.
- `uv sync --all-extras --all-groups --locked` succeeded; `just check` passed
  Ruff, Ty, and **646 tests**, with **4 upstream array-API skips**.
- `just docs-build` passed strict mode; Ruff format and `git diff --check`
  passed. No dependencies were added. Tutorial source was unchanged by M19,
  so no tutorial render was required for this milestone.

Handoff: M20 is next. M20–M21 remain pending before M15; stop this session here.

### M20 — valid diagnostic references and residual scales

**Issue 9 — undefined explained deviance.** In `workflow._evaluate_split`,
use `stability_table`'s rule: when test observed total is zero, skip the invalid
zero-mean null prediction and return `NaN` for `d2_test`. Also retain `NaN` when
a positive constant response gives zero null deviance. Keep fixed Tweedie power
1.5, the test-relative baseline for non-degenerate data, and other diagnostics.
Do not insert an epsilon or catch unrelated metric errors.

**Acceptance for 9.** A synthetic temporal experiment with claimed training
data and a claim-free test period completes with `d2_test=NaN`, finite model
deviance, O/P zero, and reconciled calibration totals. Compare D² with a
single-period `stability_table`; cover a constant-positive test rate and ordinary
non-constant data, and check model-card/comparison rendering of undefined values.
Exercise `_evaluate_split` through tuning's existing tests too. Use
`tests/test_workflow.py` and `tests/test_reporting.py`; retain sklearn deviances.

**Issue 7 — observed-rate oracle.** In `plots.plot_lorenz`, pass
`claim_amount / exposure` as the oracle ranking score while retaining aggregate
claims for the curve's ordinate and exposure for its abscissa. Omitted weights
mean unit exposure. Update the docstring: this is a hindsight ranking bound,
not a deployable model or necessarily a Gini of one.

**Acceptance for 7.** Claims `[100, 20]` and exposures `[1, 0.1]` must produce
an oracle equal to `lorenz(claims, claims / exposure, exposure)` with Gini about
`+0.0757576`. Check plotted coordinates and the legend, unit exposures, tied
observed rates, and a multi-model chart with one oracle in `tests/test_plots.py`.
Keep the core `gini`/`lorenz` algorithm unchanged.

**Issue 12 — signed logarithmic residuals.** For `logy=True`, retain the
positive-prediction panel's log y axis and use Matplotlib's native `symlog` for
the signed residual y axis. Use its documented default linear threshold
initially; callers can adjust the returned axes. Document that `logy=False`
keeps linear residuals and `bins="log"` controls density colour, not the residual
axis. No new plotting API or manual residual transform is needed. See the
[Matplotlib symlog documentation](https://matplotlib.org/stable/gallery/scales/symlog_demo.html).

**Acceptance for 12.** Extend `tests/test_plots.py` with negative, zero, and
positive residuals, weighted/unweighted and standalone/caller-supplied axes.
Render headlessly and verify displayed coordinates are finite, ordered, and
visible on both sides of zero. Checking only the scatter scale or PNG existence
is insufficient. Update the plotting guide.

**Completed 2026-09-05.** `_evaluate_split` skips the invalid zero-mean null
prediction for claim-free tests and retains `NaN` when null deviance is zero.
Other diagnostics and the fixed-power, test-relative baseline are preserved.
The oracle now orders observed rates with unit exposure when weights are omitted;
its docstring and plotting guide explain the hindsight bound. Residual y axes use
native `symlog` with the default threshold of 2 when `logy=True`.

Rendering inspection also found that Matplotlib's hexbin collection uses affine
offsets: changing only the axes scales could leave density cells outside the
plot even when transformed input coordinates looked correct. For either log
flag, both panels now store their hexagon vertices in original data coordinates
before applying native axes scales. Residual values, bin membership, and density
weights are unchanged; no manual residual transform or new plotting API is used.

Acceptance evidence:

- Before implementation, the new focused checks gave **11 expected failures**:
  claim-free workflow/reporting/tuning rejected zero null predictions; unequal
  exposures and tied rates produced wrong oracle coordinates; log residuals
  collapsed negative and zero values. Unit exposure, constant positive test
  rates, ordinary test data, and linear residual checks already passed.
- The two-policy oracle has Gini **+0.0757576**, exposure shares
  `[0, 10/11, 1]`, and claim shares `[0, 5/6, 1]`. Checks also cover unit
  exposures, tied observed rates, legend values, and one oracle across models.
- Workflow checks reconcile claim-free calibration totals and compare D² with
  a single-period `stability_table` for zero, constant positive, and ordinary
  rates. Model cards retain `nan`; comparison tables retain `NaN` and HTML
  dashboards serialize it as missing. Tuning completes with claim-free inner
  and outer holdouts, with and without returned estimators.
- Stronger collection-coordinate checks exposed **8 failures** after the scale
  change alone. After correcting the geometry, `uv run pytest -q
  tests/test_plots.py -k test_residual_scale_keeps_signed_density_visible`
  passed **16 checks** across weighting, embedded/standalone axes, and both log
  flags. Actual rendered cell centres are finite, correctly ordered, and within
  the axes and figure on both sides of zero; density totals are preserved.
  A headless rendered figure was visually inspected as well.
- `uv sync --all-extras --all-groups --locked` succeeded; final `just check`
  passed Ruff, Ty, and **673 tests**, with **4 upstream array-API skips**.
- `just docs-build` passed strict mode; Ruff format and `git diff --check`
  passed. No dependencies were added. M20 does not change tutorial source, so
  no tutorial render was required; generated output remains outside tracked
  source.

Handoff: M21 is next. Its actuarial explanations remain pending before M15;
stop this session here.

### M21 — correct actuarial explanations

Correct `examples/fremtpl2.qmd`, affected `metrics.py`/`plots.py` docstrings,
and the existing diagnostics and actuarial workflow guides. Search for repeated
claims across documentation, including API text generated from docstrings.
Keep current chart/table APIs.

**Issue 10 — measure calibration for every candidate.** Remove claims that
Gamma/Tweedie losses inherently predict below the mean and that GLMs or Poisson
GBMs automatically balance totals. Define observed rate `r`, predicted rate `mu`,
and exposure `w`. Deriving the converged, unpenalized log-link GLM intercept
equation from glum's documented deviance derivative gives
`sum(w * (mu - r) * mu**(1-p)) = 0`. For Poisson (`p=1`) this implies training
total balance; for Gamma (`p=2`) or Tweedie (`1<p<2`) it does not generally do so.
The losses target conditional means; model restrictions and fitting choices
affect achieved calibration. This is a derivation from
[glum's deviance and link definitions](https://glum.readthedocs.io/en/latest/glm.html),
not a guarantee of held-out balance.

Show training O/P for every GLM and GBM candidate. For the tutorial's explicit
burn-cost adjustment, calculate `sum(claim_amount) / sum(w * prediction)` for
every candidate from M16's training rows and freeze it before examining test
outcomes. This adjusts training totals; it need not improve test deviance or
segment calibration. Display labelled raw and adjusted holdout metrics from
the same test positions. Identify which predictions feed each chart, scoring
example, and distillation comparison. Distillation currently teaches from the
unscaled estimator: label that teacher explicitly so its fidelity is not confused
with adjusted chart predictions. Positive scaling preserves ranking but changes
level diagnostics.

**Issue 8 — compare predictions with observations.** Explain the gaps between
observed pure premium and each model's predicted pure premium within ratio
groups. Rising observations alone cannot select a model. Extreme ratio groups
contain the largest relative disagreements and may be particularly informative;
assess their exposure/claims credibility. Remove direction-only recommendations
and anchored-endpoint claims everywhere, including `double_lift_table` and
`plot_double_lift` docstrings. The
[CAS GLM monograph, section 7.2.2, pp. 78–79](https://www.casact.org/sites/default/files/2021-01/05-Goldburd-Khare-Tevet.pdf#page=88)
compares predictions with observed rates by ratio group. Its illustrated curves
are normalized; Azoic plots absolute rates, which also reveal level differences.
Explain the distinction without adding a normalization API.

**Issue 11 — distinguish level errors.** Define residuals as
`observed_rate - predicted_rate`. A constant non-zero conditional mean residual
indicates an additive discrepancy. If `observed_rate = c * predicted_rate`,
residuals equal `(c - 1) * predicted_rate`: a slope can be entirely multiplicative
and removable by one factor. Examine credible grouped mean residuals before
attributing remaining curvature to model structure. The densest band in
zero-heavy policy outcomes is not necessarily the conditional mean.

**Issue 13 — distinguish Gini measures.** Explain that Azoic computes
prediction-ordered concentration Gini, which may be negative, while pairwise
absolute-difference inequality Gini measures dispersion independently of model
predictions. The corresponding exposure-weighted inequality Gini is recovered
when ranking by observed rates. Write `G = 1 - 2 * integral(C(u), du)` with
integration from 0 to 1: twice the signed area from the concentration curve to
the diagonal. Define `u` as cumulative exposure share and `C(u)` as cumulative
claim share. The implementation integrates tied-score blocks and is equivalent
to the midrank formula; it does not evaluate pairwise differences. Correct the
related `gini` docstring's implication that perfect ranking always gives one.
Preserve the existing calculation and positive-scalar invariance.

**Acceptance.** Add small network-free numerical examples beside the revised
explanations and execute them:

- **10:** an intercept-only mean-target example, a varying-feature unpenalized
  Gamma/Tweedie counterexample, and a Poisson control. Use solver tolerances,
  not the reported totals as exact goldens; verify training-only factors and
  consistent raw/adjusted metric labels.
- **8:** observed/B rates `[10, 20, 30]` against A `[1, 20, 90]`, showing B
  matches within each ratio group despite rising observations. Use repeated
  ratios or sufficient rows so quantile ties do not erase the example's groups.
- **11:** additive `r=mu+5` and multiplicative `r=2*mu` examples, showing why
  one multiplier does not generally remove the former and exactly fixes the latter.
- **13:** forward/reversed predictions flip concentration Gini's sign while
  inequality Gini is unchanged; a hand-worked curve confirms the factor of two.

Run `just demo` and inspect rendered equations and plots. Use focused checks in
existing test modules for numerical contracts; do not test prose with complete
string assertions. Run the strict docs build for guides and generated API text.

**Completed 2026-09-05.** The tutorial, diagnostics and actuarial workflow
guides, and affected metric/plot docstrings now distinguish conditional-mean
targets from achieved calibration, compare double-lift predictions with
observations, separate additive and multiplicative residual errors, and define
signed concentration Gini separately from observed-rate inequality.

Every tutorial candidate now reports training O/P and receives its own frozen
training-only burn-cost factor. Raw and adjusted Gini, O/P, fixed-power Tweedie
deviance, and D² are shown on the same stored holdout. Charts and outcome-free
scoring use adjusted rates; run reports and MLflow retain raw metrics, and
workbook fidelity is explicitly against the raw, unscaled GBM teacher. Existing
chart/table APIs and core metric calculations are preserved.

Acceptance evidence:

- Before the tutorial change, the focused numerical checks passed and the
  tutorial regression failed because the two GLM candidates had no factors.
  After implementation, all **11 focused checks** passed in the existing
  model, metric, and workflow test modules.
- Six unpenalized log-link fits verify intercept-only mean targeting and the
  varying-feature Poisson control versus Gamma/Tweedie counterexamples, using
  solver tolerances. The synthetic tutorial regression executes the actual
  calibration/evaluation cells with non-positional index labels, changes only
  test losses, and verifies unchanged factors for every candidate. It checks
  raw/adjusted labels, raw run agreement, unchanged Gini, and adjusted level metrics.
- Repeated ratio groups retain observed/B rates `[10, 20, 30]` and A rates
  `[1, 20, 90]`, with A residuals `[9, 0, -60]`. Additive `r=mu+5` retains
  `[2.5, 0, -2.5]` after total adjustment; multiplicative `r=2*mu` becomes
  zero. Rates `[1, 3]` with exposures `[1, 2]` give inequality Gini `4/21`,
  concentration Gini `+4/21` or `-4/21` under reversed ordering, and curve
  area `17/42`, confirming the factor of two and positive-scalar invariance.
- The exact four new tutorial counterexample cells and both new guide snippets
  executed without network access. `uv sync --all-extras --all-groups --locked`
  succeeded. Final `just check` exited successfully: Ruff, Ty, and **684 tests**
  passed, with **4 upstream array-API skips**. Ruff format and `git diff --check`
  passed; `just docs-build` passed strict mode, including generated API text.
- Final `just demo` exited successfully after all **23 cells**, fitting and
  scoring the full **667,673-policy** cleaned portfolio. Stored holdout/raw
  metric agreement, adjusted training totals, scoring, raw-teacher distillation,
  workbook reproduction, and local reporting/MLflow assertions passed.
- Headless inspection found no MathJax errors or broken images. The intercept,
  burn-cost, Gini, and residual equations were visually checked. Plot review
  led to native constrained layout for the lift/calibration grid and the
  existing standalone exposure panel for double-lift; its accompanying table
  reports exposure and claim totals for all ten ratio groups. No dependencies,
  custom theme assets, or plotting APIs were added. Generated HTML, images,
  data, workbooks, and tracking state remain ignored; Quarto's temporary notebook
  was removed by the completed render.

Illustrative final tutorial results (Tweedie deviance uses power 1.5):

| Model | Training O/P factor | Raw holdout O/P | Adjusted holdout O/P | Raw deviance | Adjusted deviance |
|---|---:|---:|---:|---:|---:|
| `direct-tweedie-glm` | 0.998170 | 1.022067 | 1.023942 | 75.338331 | 75.340078 |
| `frequency-severity-glm` | 1.007749 | 1.032296 | 1.024358 | 75.237864 | 75.233317 |
| `tweedie-lightgbm-tariff` | 1.096248 | 1.123572 | 1.024925 | 75.285399 | 75.119374 |
| `tweedie-lightgbm` | 1.150219 | 1.178104 | 1.024243 | 74.721321 | 74.405403 |
| `frequency-severity-gbm` | 1.144758 | 1.174354 | 1.025853 | 74.560943 | 74.327163 |

Adjusted training O/P is one for every candidate and each holdout Gini is
unchanged. The direct GLM's holdout deviance gets slightly worse after adjustment,
illustrating why training balance is not a guarantee of better held-out fit.
These rendered values are evidence, not exact solver goldens in automated tests.

Handoff: **M15 is next.** Repeat M14's distribution builds and isolated CLI
smokes on the corrected source before publication. Stop this session here.

### Completion and release evidence

- For each implementation milestone, add the relevant counterexample checks
  first and confirm they fail for the expected reason where behaviour is
  defective. Documentation corrections need executable numerical evidence.
  Then implement that milestone and run its focused tests.
- Run `just check` before each handoff and `just docs-build` when guide/API
  documentation changes. Run `just demo` for tutorial-changing milestones;
  Quarto is an external prerequisite and real-data fetching is limited to this
  manual render. Automated checks remain synthetic and network-free.
- Record behaviour changes, executed commands/results, and any remaining
  limitation under the milestone. Mark it ☑ only when acceptance checks pass;
  stop after that milestone. No new dependencies, subpackages, generated assets,
  or compatibility layer are part of this plan.
- Before M15, all thirteen issue checks must pass together, the corrected
  tutorial and strict docs build must succeed, and M14's distribution build and
  isolated CLI smoke checks must be repeated for the corrected source. Earlier
  artifacts and contaminated tutorial results are not release evidence for these
  fixes. Keep generated data, charts, reports, workbooks, and HTML ignored.

## Demo tariff flow — 2026-09-05

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

### M23 — evaluate the exported tariff against claims (completed 2026-09-06)

Distil the structured teacher on training rows with copied preprocessing. Export
with `recalibrate=False` and training metadata. Apply workbook factors using the
existing recipe to fitted-pipeline-transformed features; no standalone loader.
Check workbook/student agreement on train/test at existing tolerance. Finish with
four rows: direct GLM, raw GBM, structured teacher, applied workbook; show weighted
Tweedie deviance at 1.5, D², concentration Gini, O/P, predicted total claims, and
common observed claims/exposure. Add calibration panels, overlaid Lorenz curves,
and age comparisons with identical training bins. Separately show metrics adjusted
by each model's own frozen training O/P (including workbook training predictions);
the workbook adjustment is an external multiplier. Separate teacher/student deviance
and total-ratio fidelity from claims performance. Describe gains/losses without
assuming distillation worsens performance or claiming superiority from one split.
Repeat tutorial/visual, partition/mapping/scaling/metric, suite, docs, and diff checks.
No new dependencies, public interfaces, binning algorithm, or automated selection.

### M22 acceptance evidence — 2026-09-06

- `just check`: **685 passed, 4 skipped**, with Ruff and production Ty green.
  Ordered interval regression covers alphabetical traps, unused categories,
  missing rows, and reconciled exposure, claims, and predicted totals. The existing
  tutorial leakage test now executes the separated setup/calibration cells and
  still proves holdout outcome changes cannot change training factors.
- Final `just demo`: all **27 cells** passed on **667,673 policies**, with
  **534,138 training / 133,535 test** rows. Main and appendix runs assert identical
  fingerprints and stored positions. An AST comparison against the pre-M22 source
  also confirms every ModelSpec and PreprocessingSpec is unchanged.
- All nine fitted-group training summaries reconcile policy counts, exposure,
  claim counts, and losses. Primary held-out GLM one-ways reconcile exposure,
  losses, and predicted totals. Fixed-policy age inputs preserve every other
  feature/exposure, and predictions agree within each bin at absolute tolerance
  1e-10. Training-fitted mappings remain unchanged.
- Raw run metrics and calibration tables reproduce fresh predictions; every
  training-adjusted O/P is one and positive scaling preserves held-out Gini.
  Workbook factors plus fitted preprocessing match the student on both training
  and test rows (`rtol=1e-6`, `atol=1e-8`), with positive finite predictions and
  copied teacher mappings checked explicitly.
- Raw holdout deviances reproduce the M21 values to six decimals: direct GLM
  **75.338331**, structured GBM **75.285399**, raw GBM **74.721321**, appendix
  frequency–severity GLM **75.237864**, and frequency–severity GBM **74.560943**.
- Visual inspection confirms numeric interval order, raw GLM scale labels,
  non-monotonic fixed-policy steps at fitted boundaries, secondary raw-age
  composition swings, three-model comparison legends, observed curves, and
  calibration/Lorenz references. Headless inspection found no broken images or
  MathJax errors. `just docs-build` and `git diff --check` pass. Generated HTML,
  charts, workbooks, reports, data, and tracking artifacts remain ignored.

Handoff: **M23 only next**. Add the final four-model claims-based tariff
comparison, training-only export metadata, separately adjusted workbook metrics,
and separate fidelity presentation as specified above. M15 remains after M23.


### M23 acceptance evidence — 2026-09-06

- Export uses `X=fit_X` and `recalibrate=False`. Existing workbook application
  applies the read factors after copied fitted preprocessing, agrees with the
  student on train/test (`rtol=1e-6`, `atol=1e-8`), and retains positive finite rates.
- Two four-row claims tables compare direct GLM, raw GBM, structured teacher,
  and applied workbook on the same **133,535 test policies**, **70,511.873650
  exposure**, and **10,033,849.49 observed claims**. They report weighted Tweedie
  deviance at 1.5, D², concentration Gini, O/P, predicted claims, and shared totals.
- Every adjusted candidate uses its own frozen training O/P. The workbook's
  external factor is **1.093724601**; the workbook itself remains unadjusted.
  Extended synthetic tutorial regression checks all eight metric rows and proves
  changed holdout claims cannot change the workbook factor or applied rates.
- Raw deviances: direct GLM **75.338331**, raw GBM **74.721321**, structured
  teacher **75.285399**, applied workbook **75.279827**. The original three
  reproduce M22. Adjusted teacher/workbook deviances are **75.119374 / 75.146789**:
  distillation does not have a predetermined direction of claims performance.
  Teacher/student deviance and total-ratio fidelity reproduce both pipeline and
  workbook metadata and are displayed separately from claims diagnostics.
- `uv sync --all-extras --all-groups --locked` passed. `just check`: Ruff and
  production Ty green, **685 passed, 4 upstream array-API skips**. The focused
  tutorial regression passed. `just docs-build` passed strict mode.
- `uv run quarto render examples/fremtpl2.qmd --to html --execute --no-cache
  --execute-daemon-restart` completed all **32 cells**, including the executable
  appendix, on **667,673 policies / 534,138 training rows**. Execution was fresh;
  only deterministic pinned source-data downloads/joins were reused.
- Visual inspection checked both four-panel calibration scales, overlaid Lorenz
  references and four-model legends, and driver/vehicle-age comparisons with
  identical ordered training bins. Reconciliation and frozen-mapping assertions
  passed. Headless HTML inspection found **zero broken images and zero MathJax
  errors**. New figures use responsive 700-pixel notebook displays, preserving
  full-resolution PNGs; the final fresh HTML was visually checked after this fix.
  `git diff --check` passed; generated outputs remain ignored.
- No dependencies, public interfaces, model settings, or binning algorithms changed.

Handoff: **M15 only next**. M23 is complete; publication is not part of this session.
