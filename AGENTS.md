# Agent instructions

Azoic is a scikit-learn-compatible toolkit for non-life technical tariff and
pure-premium modelling. It is not reserving, fraud, AutoML or policy administration.

## Start here

1. Read [current work and latest checkpoint](development/README.md) on a new
   session or after compaction. It is the sole current-status authority.
2. Read [contributor setup and checks](CONTRIBUTING.md) before running commands.
3. Read the relevant [design contracts](development/design.md) before changing
   architecture, validation, persistence, evaluation or tariff operations.

Implement exactly one pending milestone per session: mark it ◐ before work,
run its acceptance checks, mark it ☑ only when green, then stop with a handoff.
Resume in-progress work before following the declared delivery order. Explicit
user scope takes precedence; reviews do not authorize implementation. Do not
start another milestone, release or deployment automatically.

Update the current-work checklist and checkpoint after meaningful chunks and
before handoff: changes, checks actually run/results, remaining work, blockers
and exact next action. Leave interrupted or unverified work ◐. A planning session
records pending work without starting implementation. Preserve earlier evidence
in the archive, but never treat archived instructions or permissions as current.

## Repository map

- `src/azoic/`: 13 flat Python modules; see the design reference for ownership.
  No `utils.py` or new subpackages without a concrete consumer and design review.
- `src/azoic/.agents/skills/`: packaged user skills, ordinary data directories;
  do not duplicate them as repository-root installations.
- `tests/`: synthetic, seeded tests and installed-distribution smokes.
- `docs/`: user-facing getting started, guides and reference; default Zensical theme.
- `examples/`: executable Quarto book sources; generated artifacts stay ignored.
- `development/`: current work, durable design and historical archive; not site content.

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
  Document current behavior; describe compatibility changes in release notes.
- **Format**: ruff defaults, double quotes, line-length 100, py312 target.

## Actuarial rules

1. Exposure is a **weight** for pure premium: `y = claim_amount/exposure`,
   `sample_weight=exposure`. Estimator targets, scores, and predictions use
   this rate unit. Use `offset=log(exposure)` ONLY when
   `y = claim_amount` (aggregate). Never mix.
2. Frequency: `y = claim_count / exposure`, `sample_weight=exposure`, Poisson.
3. Severity: fit on `claim_count > 0` only (Gamma needs `y > 0`). The filter
   lives INSIDE `FrequencySeverityModel.fit`.
4. LightGBM `tweedie_variance_power`: `1.0 <= p < 2.0` — validate during
   `fit`, including after `set_params`.
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

## CI and delivery

- Preserve read-only CI contents permissions, locked all-extras/groups Python
  3.12 checks, strict docs and wheel/sdist smokes. Runtime-only artifact jobs use
  metadata-resolved low compatible direct versions on Python 3.12 (asserting
  glum 3.4.1 and Typer 0.27.1 floors) and current compatible wheels on Python 3.14.
  Only Azoic's sdist may build from source; check dependencies and print versions.
- Starter CI runs the exact documented Python/YAML outside the checkout on Linux
  and Windows/Python 3.12, against released 0.5.0 and a checkout-built current wheel.
  Preserve workbook/Python/config agreement. This is not full Windows-suite coverage.
- Installed wheel/sdist smokes cover models, preprocessing, persistence, public
  composition, version, packaged skills and all eleven CLI command helps.
  Checkout-wheel starter jobs also test Linux skill links and Windows copies.
  Keep Library Skills 0.0.20 pinned in installation checks, never runtime dependencies.
  Reconcile every skill `metadata.azoic-version` string with package metadata at
  release time; stale guidance must never silently upgrade dependencies. Live agent
  trials remain outside CI and do not replace practitioner observations.
- Main-branch documentation CI renders real-data tutorials and deploys Pages.
  Keep fixed `pages` concurrency cancellation and real-data fetching outside PR tests.
- Release tags must equal `v` plus package version. Private settings, tagging and
  publication require explicit authorization. Preserve existing tags/artifacts;
  historical authorization in archived records grants no new delivery permission.
- Use Conventional Commit prefixes `feat:`, `fix:`, `chore:`, `docs:` or `test:`;
  Ruff and pytest must be green before committing. Do not commit secrets, large data
  or execution state. Update these instructions and the relevant development page
  when layout, commands or conventions change.
