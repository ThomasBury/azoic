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

## Milestone execution

> Implement exactly one pending milestone per session. Mark it ◐ before implementation, run its acceptance checks, mark it ☑ only when green, then stop with a handoff. Do not start the next milestone automatically.

On a new session or after context compaction, read `PROGRESS.md`'s **Current
focus**, the active milestone, and its latest checkpoint before editing. Resume
an in-progress milestone first; otherwise use the explicit delivery order, not
the lowest milestone number or an older handoff. The focused documentation
revision M43–M44 is complete, following M40–M42. M45 preprocessing fixes are
complete and merged in PR #1; M15 published Azoic 0.5.0 on PyPI and GitHub
on 2026-10-17. WP5 ergonomics passed local acceptance on 2026-10-23; see Current
focus for its PR delivery. Do not start another WP or release automatically.
M46 adopts ARFS-style univariate LightGBM preprocessing; see Current focus for
its checkpoint. Tree methods require outcomes and use native missing routing;
quantile/rare remain explicit alternatives. Changed tree mappings require an
explicit missing destination; learned tree intervals use `<=`, manual/quantile
intervals are lower-inclusive. M47 establishes source-to-target accounting and
target interpretation in the portfolio chapter, preserving loader rules;
professional review and predictive comparisons remain separate.
M48 completed selection and target sensitivity in that chapter: use the population
passing all other rules, fixed Area/age strata and identical retained IDs across
claim caps. Missing-cost scenarios are assumptions only; never change loader rules
or model inputs. Professional review and predictive comparisons remain pending.
M49 completed the engineering baseline; continue one phase per session (M49–M55).
The rule ownership/evidence map and diagnostic-extension baseline live in PRD
section 3; phase scope is in section 6 and execution evidence in PROGRESS.
Keep row exposure floors, explicit model weights (including severity counts),
ranking weights and diagnostic segment totals as separate policies. M49 records
the baseline; M50 completed faithful and failure-safe tariff export. Export
supports native bins/groups, workflow column removal and passthrough; other
transforms must fail before opening workbooks. Preserve generic distillation
transforms, preserve existing destination permission bits and replace only fully
saved sibling workbooks. M51 verifies glum 3.4.1 and Typer 0.27.1 floors,
retains locked Python 3.12 full checks and adds metadata-based low-version
Python 3.12 and Python 3.14 wheel/sdist runtime smokes. Python metadata support
does not imply every allowed stack is tested. M52 shares portfolio outcome
validation in `data._validate_outcomes` across workflow/tuning and FSM; retain
schema, supplied-rate and severity checks at their boundaries. Calibration
counts are aligned 1D vectors; their validation must not impose portfolio row
floors or count/amount consistency on diagnostic segments. M53 separates
estimator/input construction, fixed-shape split evaluation and final run
assembly. Trials consume split scores without public result snapshots,
training diagnostics or provenance; workflow and stability share fixed-power
Tweedie arithmetic while retaining their warning/rejection policies.
M54's extension contract and M55's independent maintainer exercise are planned
in PRD section 6; do not extract results, publish a checker or widen
`ModelSpec.kind` in advance.
Independent maintainer validation remains pending for M55.
Current focus is the authority for the active/next milestone. Read
`PREPROCESSING_FIX_PLAN.md` for the verified bugs, regression scope, PR delivery,
and release reconciliation. The scope is mirrored in `PRD.md` section 6.

Update the milestone checklist and checkpoint after each meaningful chunk and
before handing off: changes, checks actually run and their results, remaining
work, blockers, and the exact next action. Leave interrupted or unverified work
◐. Keep historical evidence; `PROGRESS.md` is the execution record and `PRD.md`
defines scope. A planning session records pending work without starting it.

## Setup commands

Registry onboarding uses `uv add azoic==0.5.0` in the user's project.
Checkout onboarding uses `uv sync` and `uv run` from the repository root;
install optional integrations with `uv sync --extra NAME`. Contributor checks
are separate from the first-model path.

- Install runtime only: `uv sync --no-dev`
- Install default development environment: `uv sync`
- Install everything: `uv sync --all-extras --all-groups`
- Install tutorial stack: `uv sync --group demo --extra mlops`
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
  metrics.py        # gini, lorenz, calibration_table, stability_table, one_way_table, double_lift_table; sklearn deviances re-exported
  validation.py     # make_strata, temporal_split
  plots.py          # plot_lorenz, plot_lift, plot_calibration, plot_one_way, plot_double_lift, plot_actual_vs_predicted (matplotlib)
  tariff.py         # distill_gbm; export_tariff(glm_or_pipeline, path)
  workflow.py       # ExperimentConfig, preprocessing/freq-sev YAML, run_experiment
  reporting.py      # model_card, comparison_table/dashboard
  mlops.py          # log_run (mlflow, lazy import)
  tune.py           # tune_experiment (optuna, lazy import) -- v0.2 part 1 / M7
  cli.py            # Typer entry point
tests/              # pytest; synthetic portfolio fixture in conftest.py
examples/           # numbered Quarto tutorial book (only .qmd/.yml committed)
```

13 flat modules. No `utils`. No subpackages. Don't create either without
checking `PRD.md` sections 3 and 9.

Documentation is task-first:

```
docs/
  getting-started/  # installation and one network-free first model
  guide/            # workflow plus five focused task guides and tutorial bridge
  reference/        # generated Python API, config/CLI schema, and glossary
  javascripts/      # official Zensical MathJax integration only
examples/*.qmd        # numbered Quarto book chapters; linked, not restyled, by Zensical
examples/_quarto.yml  # main path and optional recipes; only sources committed, _book/ ignored
```

## Code style

- **Validation** — sklearn >=1.6; prefer public `sklearn.utils.validation.validate_data`,
  `check_array`, and `check_consistent_length`; reuse `_pop_weight` / `_as_arrays`.
  Schema-only DataFrame checks (`skip_check_array=True`) preserve categoricals
  but do not validate targets/weights/values. Keep strict-vector and actuarial
  domain guards, plus the minimal schema guard for optional special columns.
  Do not import private sklearn validators or create a validation framework.
- **sklearn API** — `fit`/`transform`/`predict`, fitted attrs end in `_`, no
  logic in `__init__`, params explicit **never** `**kwargs` (LightGBM kwargs
  break `get_params`).
- **Estimator units** — every estimator takes pure-premium rate targets in
  `fit`/`score` and predicts rates. `FrequencySeverityModel.fit(X)` may
  derive its components from the outcomes inside `X`; when `y` is supplied,
  it must equal `claim_amount / exposure`.
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
- **Documentation** — keep Zensical's default theme; use cards only on section
  hubs; JavaScript is limited to the official MathJax helper/runtime; never
  commit generated site, tutorial, chart, or fetched-data artifacts.
  Before the first public release, document current behavior without a
  version-migration guide.
- **Format**: ruff defaults, double quotes, line-length 100, py312 target.

## Actuarial rules (do not violate; full context in PRD.md sections 4-5)

1. Exposure is a **weight** for pure premium: `y = claim_amount/exposure`,
   `sample_weight=exposure`. Estimator targets, scores, and predictions use
   this rate unit. Use `offset=log(exposure)` ONLY when
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
12. Exposure is at least one day (`MIN_EXPOSURE = 1/366`, `EXPOSURE_FLOOR`
    with 0.1% tolerance): enforced at the portfolio boundary, preprocessing fit,
    FSM fit, popped exposure columns, calibration/one-way segment sums, and tariff
    recalibration. Explicit `sample_weight` is exempt (severity routes claim
    counts). Zero-weight rows stay legal for ranking curves only.

## Testing

- `pytest`, seeded synthetic portfolio fixture in `tests/conftest.py`
  (`make_synthetic_portfolio(seed=42)`).
- Every estimator/transformer runs
  `sklearn.utils.estimator_checks.parametrize_with_checks`. The wrappers
  explicitly expect `check_supervised_y_2d` to fail because Azoic rejects
  column-vector targets; a direct regression enforces the strict 1D contract.
- No network, no S3, no real data in automated tests. Real-data fetching is
   permitted only during local or main-branch Actions rendering of the
   `examples/` tutorial book.
- New module -> new `tests/test_<module>.py` with at least one runnable
  check.
- Keep tutorial HTML, Quarto caches/support files, fetched data, workbooks,
  reports, and MLflow state ignored; only the `.qmd` is source-controlled.
- Tutorial cleaning caches pair `fremtpl2_joined_v3.parquet` with
  `cleaning_audit_v1.csv`; rebuild both from cached raw inputs if either is
  missing. Delete both after changing the claim cap or cleaning rules.
- Tutorial chapters create their own artifacts; shared setup uses `include: false`.
  Keep the direct GLM and raw-feature GBM on the main path; construct the
  structured teacher explicitly in optional distillation/tuning. Show one
  numeric bin and categorical group before optional full inspection. Fold
  verification code, retain assertions, label prediction scales, and show CLI
  commands with subprocess plumbing hidden. Mark deeper sections and later
  recipes optional, and supply figure alternative text. The synthetic
  reporting assembly smoke test covers setup through MLflow; full sequential
  rendering and isolated chapter rendering are separate manual checks.
- Run `just check` (or `uv run ruff check . && uv run ty check && uv run pytest`) before
  finishing any task.

## CI workflows

- `.github/workflows/ci.yml` validates PRs and main pushes on Python 3.12 with
  read-only contents permissions: locked all-extras/groups sync, Ruff, Ty,
  pytest, strict docs, distributions, and installed wheel/sdist model,
  preprocessing, version, and all-five-command CLI smokes.
  Separate runtime-only jobs reuse that smoke outside the checkout for wheel
  and sdist: low compatible direct dependencies from wheel metadata on Python
  3.12 (`lowest-direct`, asserting exact glum/Typer floors), current compatible
  dependency wheels on Python 3.14. Only Azoic's own sdist may build from source;
  installs resolve without `uv.lock`, run `uv pip check` and print their versions.
- `.github/workflows/docs.yml` renders the real-data tutorial and deploys Pages
  on main pushes with locked sync; the fixed `pages` concurrency group cancels
  superseded runs. Real-data rendering stays outside PR validation.
- Release publication remains in `.github/workflows/release.yml`; its tag must
  equal `v` plus the package version before artifacts can be published. Private
  settings, tagging, and publication require explicit authorization. The 2026-10-17
  request authorizes M45 Git delivery and subsequent M15 release/publication once
  its separate release PR and acceptance checks are green; do not ask again for
  that same scope. Keep version changes in M15 and preserve existing release tags.

## PR / commits

- Commit prefixes: `feat:`, `fix:`, `chore:`, `docs:`, `test:`.
- ruff + pytest must be green before commit.
- If you change layout, commands, or conventions — update this file AND
  `PRD.md` / `PROGRESS.md` to match. Living docs.
- Don't commit secrets, large data, or notebooks' execution state
  (`.ipynb_checkpoints/` is gitignored).
