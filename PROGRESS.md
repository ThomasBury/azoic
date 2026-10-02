# Azoic — Progress

> Living tracker. Mirrors `PRD.md` section 6 milestones. Update after every
> chunk of work.

Legend: ☐ pending · ◐ in progress · ☑ done

> Implement exactly one pending milestone per session. Mark it ◐ before implementation, run its acceptance checks, mark it ☑ only when green, then stop with a handoff. Do not start the next milestone automatically.

## Current focus

- **Goal:** complete prerelease fixes before the separate M15 release review.
- **Active milestone:** none. M42 ☑ completed 2026-10-02; M15 is next.
- **State:** M40–M42 prerelease fixes are locally green. PR/main CI validates
  Python 3.12 with read-only permissions, locked all-extras/groups sync, source
  checks, strict docs, distributions, and installed artifact smokes. Pages uses
  locked sync and cancels superseded runs in the fixed `pages` group. Final
  `just check`: Ruff/Ty green, **1051 passed, 4 upstream skips, 2 expected
  strict-target failures**. Prior work is preserved. Remote PR execution and
  Pages cancellation remain unverified until a separately authorized push.
- **Delivery order:** M40 → M41 → M42 → M15, one green milestone per session.
- **Resume here:** in a new session read M42's completion checkpoint and the
  current working tree, then perform only the separate M15 release review.
  Private settings, push, tagging, and publication remain separately authorized.

This section and the delivery order below supersede historical statements that
M15 is next. Completed milestones and their evidence remain historical records.

## Prerelease fixes — 2026-10-02

Review evidence and scope come from the accepted three-unit plan. pandas 2
support ends; estimator signatures and actuarial rate/weight units remain.
No compatibility shim or new runtime dependency is required.

| Status | Milestone | Scope |
|---|---|---|
| ☑ | M40 — pandas 3 migration and distribution checks | pandas ≥3.0, string conversion, Copy-on-Write tests, categorical regressions, installed artifact smoke checks, migration guidance |
| ☑ | M41 — documentation matches implemented behavior | training-only CLI recalibration, DatasetSpec exposure routing/conflicts, standalone HTML dashboards, absolute-rate lift, rendered pages and local links |
| ☑ | M42 — pre-merge validation and controlled Pages runs | Python 3.12 PR/main checks with read permissions, all locked extras/groups, Ruff/Ty/tests/docs/build/artifact checks, fixed pages concurrency with cancellation, locked Pages sync |

### M40 — pandas 3 migration and distribution checks

- [x] Raise pandas minimum to 3.0 and regenerate the lock retaining unrelated versions.
- [x] Convert native `str`, nullable strings, and object columns at shared model
  boundaries; preserve numerics, categorical metadata, and caller inputs.
- [x] Request copies in tests that mutate pandas arrays; replace deprecated
  categorical construction while retaining Copy-on-Write.
- [x] Check categorical influence, tariff extraction, order, and unused levels.
- [x] Add runtime-only `tests/smoke_distribution.py`; run it plus CLI help for
  independently resolved wheel and sdist installs outside the checkout.
- [x] Correct installation/model-choice guidance and remove pandas 2 limitation.
- [x] Pass `just check`, `just docs-build`, `git diff --check`; execute the exact
  first-model example and verify its categorical predictor affects predictions.
- [x] Complete full tutorial and isolated scoring-chapter renders under pandas 3;
  record successful exit statuses before marking complete.

Checkpoint — kickoff 2026-10-02: read Current focus, M39 evidence, shared helper
and its callers, release validation, and environment. Current lock uses pandas
2.3.3; existing uncommitted changes saved to `/tmp/azoic-before-m40.patch`.
Context7 and pandas migration/Copy-on-Write guidance confirm selecting
`object` plus `string` and explicitly copying arrays intended for mutation.
Next: add behavioral regressions, migrate the environment, reproduce failures,
then fix the shared helper and run acceptance. M41/M42 remain pending.

Checkpoint — implementation 2026-10-02: pandas is locked at **3.0.6**.
MLflow **3.15.1** cannot be retained: its `pandas<3` requirement makes the new
contract unsatisfiable. The related mlflow/mlflow-skinny/mlflow-tracing packages
therefore move to **3.16.1**; pandas no longer needs pytz. Other versions remain.
Shared conversion selects object/string and frequency–severity prediction now
uses the same conversion. Nine of 17 new regressions failed before the repair;
all **17 pass** afterward, including categorical influence, numeric/input
preservation, missingness, ordered/unused vocabularies, and tariff extraction.
Mutating exposure tests request copies. Release validation adds runtime-only
wheel/sdist model smokes outside checkout alongside CLI help. Strict docs,
Ruff, Ty, and distribution build passed. The exact first-model example ran and
its fixed-policy rural/suburban/urban rates were **244.478 / 446.861 / 657.109**.
The full suite and full tutorial render are running. An initial smoke assertion
was too strict for uv's symlinked package cache; installed-file ownership now
uses distribution metadata. Next: finish suite, correct any remaining migration
failures/warnings, rerun artifact smokes, complete isolated scoring render, and
run final acceptance gates. M40 remains ◐.

Checkpoint — acceptance repairs 2026-10-02: the migrated full suite reported
**1050 passed, 1 failed, 4 skipped, 2 expected failures** (302.34 s). The failure
was a third test mutating a read-only target array before calling the estimator;
it now requests `copy=True`. Two pandas deprecation warnings in the category
fingerprint regression now use `cat.set_categories` without changing values.
All **7 focused repair checks passed**, without those warnings. Both separately
resolved Python **3.12** wheel and sdist installs passed runtime-only behavioral
checks and CLI help outside the checkout; metadata verifies installed imports
and `0.4.1` version agreement with pandas **3.0.6**. Authored local links resolve
and all four changed Python files pass Ruff format checks. Final `just check`
and full tutorial render are running. Next: complete those runs and the separate
isolated scoring chapter, then record exit statuses and mark M40 green only
when all acceptance checks pass.

Checkpoint — tutorial environment 2026-10-02: the first full render exited
**1** in chapter 05 because the existing ignored tutorial MLflow SQLite store
had the 3.15.1 schema. Preserved a consistent, integrity-checked backup at
`/tmp/azoic-m40-mlflow-before-3.16.1.db`, then used the documented
`uv run mlflow db upgrade sqlite:////home/bsatom/Documents/azoic/examples/_artifacts/fremtpl2/mlflow.db`.
Migration succeeded (exit **0**); no historical runs were deleted. Installation
troubleshooting now documents this local upgrade step. A fresh `just demo`
full-book render is running; final suite and isolated scoring render remain
the next acceptance checks. The failed render log is preserved at
`/tmp/azoic-m40-tutorial-before-db-upgrade.log`.

Checkpoint — final code gate 2026-10-02: `just check` exited **0** with
Ruff and production Ty green, **1051 passed, 4 upstream array-API skips,
2 expected strict-target failures**, in **281.47 s**, with no pandas warnings.
Strict `just docs-build` exited **0** after the local MLflow troubleshooting
addition. Distribution behavior/CLI checks, the exact first model, Ruff format,
authored local links, release YAML/shell syntax, and `git diff --check` are green.
Remaining acceptance is the full `just demo` rerender after the backed-up local
store migration and a separate fresh scoring-chapter render. M40 stays ◐ until
both finish; M41/M42 and release remain pending.

Checkpoint — isolated scoring acceptance 2026-10-02: copied byte-identical
`.qmd`/`.yml` tutorial sources plus the paired joined-data/cleaning-audit inputs
to `/tmp/azoic-m40-scoring`, with an empty scoring artifact directory. Ran
`uv run --project /home/bsatom/Documents/azoic quarto render /tmp/azoic-m40-scoring/examples/04-scoring-tariff.qmd --to html --execute --no-cache --execute-daemon-restart`.
All **21 cells** passed with a fresh kernel under the migrated environment;
render exited **0** and wrote its own `_book/04-scoring-tariff.html`. It shares
no generated scoring artifacts with the full render. The upgraded tutorial
tracking database also passed integrity checking and retained all **102 prior
runs**. Full book acceptance is the only remaining item; M40 stays ◐.

### M40 completion checkpoint — 2026-10-02

Changed: pandas minimum **3.0**, lock **3.0.6**; shared object/string conversion
for GLM, GBM, and frequency–severity fit/predict/score; three intentional array
mutations request copies; category fingerprint tests use the native setter.
Added 17 category/missingness/metadata/input-preservation regressions and the
runtime-only `tests/smoke_distribution.py`. Release validation now runs model
smokes plus CLI help for independently resolved wheel/sdist installs outside
checkout. Installation and model-choice guidance explain automatic conversion,
direct LightGBM backend preparation, pandas 2 support ending, and existing
local tutorial database migration. M40–M42 scope and delivery order are recorded
in PRD/AGENTS and here; pre-existing M34–M39 changes remain intact.

Acceptance evidence:

- `uv sync --locked --all-extras --all-groups` and `uv lock --check` exited **0**.
  Only pandas and the necessary MLflow trio changed versions; pandas dropped
  pytz. MLflow 3.15.1 could not resolve against pandas ≥3, so its three related
  packages are **3.16.1**. No new dependency, compatibility shim, module,
  estimator signature, actuarial unit, or Copy-on-Write override was introduced.
- The 17 new checks reproduced **9 failures / 8 passes** before the repair and
  all pass afterward. Final `just check` exited **0**: Ruff/Ty green,
  **1051 passed, 4 upstream array-API skips, 2 expected strict-target failures**
  in **281.47 s**, without pandas warnings. Existing strict-target behavior
  remains intentional.
- `just docs-build` exited **0** in strict mode; affected authored local links
  resolve. Ruff format check on all four changed Python files, release YAML
  parsing and smoke shell syntax, and `git diff --check` passed.
- `uv build` exited **0**. Runtime-only wheel and sdist model/import/version
  checks and both CLI help commands each exited **0** on Python **3.12** outside
  checkout with fresh, independently resolved dependencies (pandas **3.0.6**).
  Imports are verified against installed distribution files, including uv's
  symlinked package cache, and version metadata agrees at **0.4.1**.
- Executed the exact first-model documentation example in `/tmp` under the
  migrated environment. Its region predictor is retained in backend category
  metadata and fixed-policy rural/suburban/urban predictions are
  **244.478 / 446.861 / 657.109**, proving informative categorical influence.
- Final **`just demo` exited 0**, freshly executing all **136 cells**
  across ten executable chapters plus the index, with the freMTPL2 chapters on
  **667,673 policies**, and creating `examples/_book/index.html`. The first run's
  local MLflow schema failure is preserved above; after a consistent backup,
  its documented database migration exited **0**. Database integrity passed
  and all **102 prior runs** remain. No tracked tutorial source changed in M40.
- The separate scoring-chapter command recorded above exited **0**, executing
  all **21 cells** with a fresh kernel from byte-identical temporary tutorial
  sources, paired cached cleaning inputs, and an empty artifact directory.
  Its generated outputs are independent of the full book. Tutorial output,
  charts, data, workbooks, and tracking state remain ignored.

Remaining: M41 documentation parity and M42 CI/Pages controls, followed by the
separate M15 trusted-publisher/release review. M40 blockers: none. No commit,
push, tag, publication, or private configuration change was performed.

Exact next action: start a new session, mark **M41 only** ◐, trace CLI export
calibration, DatasetSpec exposure overrides, dashboard return values, and lift
units against current source; apply the minimum prose corrections and verify
examples/local links and rendered affected pages. Run `just check`, strict docs,
and diff checks, then stop after M41's green handoff. Do not start M42 here.

### M41 — documentation matches implemented behavior

Make minimum prose corrections against current source. CLI export recalibrates
on training observations; library callers supply a calibration frame and keep
evaluation separate. Exposure comes from DatasetSpec and conflicting non-null
model overrides raise. Dashboards return standalone HTML strings. Lift uses
absolute observed/predicted rates. Run all-unit checks plus strict docs, inspect
affected rendered pages, and verify authored local links.

- [x] Trace CLI/library tariff calibration, DatasetSpec exposure routing,
  dashboard outputs, and lift units against current implementations and tests.
- [x] Correct stale exposure override, dashboard, lift, and recalibration prose;
  retain existing accurate training-only CLI and caller-selected library guidance.
- [x] Verify relevant documentation examples and authored local links; inspect
  affected rendered pages after a strict build.
- [x] Pass `just check`, `just docs-build`, and `git diff --check`; record a green
  completion checkpoint and hand off to M42 without starting it.

Checkpoint — kickoff 2026-10-02: read Current focus, M40 completion evidence,
M41 scope, and the existing working-tree changes. Preserve all prior milestone
work. Next: trace tariff export, exposure routing, dashboard return values, and
lift units; correct only affected documentation, then run the required checks.
M42 and release remain pending.

Checkpoint — prose corrections 2026-10-02: traced `ModelSpec.effective_params`
and `build`, CLI `export_tariff`, library `export_tariff`,
`comparison_dashboard`, and `plot_lift`, plus their existing regressions.
Five documentation pages now explain conflicting non-null exposure overrides,
standalone HTML strings with embedded Plotly JavaScript, absolute-rate lift,
and training-only CLI versus caller-selected library calibration. Existing
accurate tariff guidance is preserved. Locked all-extras/all-groups sync and
the initial diff check exited **0**. Next: run the full suite and strict docs,
execute relevant examples, inspect rendered content, and verify local links.
No runtime code, dependency, theme, or workflow change is needed for M41.

### M41 completion checkpoint — 2026-10-02

Changed: minimum prose corrections in `docs/guide/operations.md`,
`docs/guide/diagnostics-visualization.md`, `docs/reference/configuration-cli.md`,
`docs/reference/glossary.md`, and `docs/reference/workflow-operations.md`.
Exposure routing now states that omitted/null overrides use DatasetSpec,
matching values are accepted, and conflicting non-null values raise, including
frequency–severity's outer special-column params. Dashboards return standalone
HTML strings with embedded Plotly JavaScript. Lift plots absolute observed and
predicted rates. The glossary now reflects training-only CLI recalibration and
caller-selected library calibration frames with separate evaluation rows.
Existing accurate guide/reference tariff guidance and prior changes remain.

Acceptance evidence:

- `uv sync --locked --all-extras --all-groups` exited **0**.
- `just check` exited **0**: Ruff and production Ty green; **1051 passed,
  4 upstream array-API skips, 2 expected strict-target failures**, in **238.40 s**.
  Log: `/tmp/azoic-m41-check.log`. Existing CLI regressions cover direct/distilled
  exports with both recalibration settings and unchanged holdout boundaries.
- `just docs-build` exited **0** with no issues in strict mode.
  Log: `/tmp/azoic-m41-docs.log`. Inspected generated content and local browser
  screenshots for all five affected pages; no theme or JavaScript edits.
- Executed the exact reporting, partition-recovery, and diagnostic-table Python
  snippets with seeded synthetic data. Checked GLM/GBM omitted, null, matching,
  and conflicting exposure overrides; dashboard HTML embeds its JavaScript
  without external script sources; lift line values equal absolute table rates;
  library calibration reproduces the caller-selected training claim total.
  All passed; example artifacts stay in `/tmp/azoic-m41-examples`.
- `uv run python /tmp/azoic-m41-verify-docs.py` exited **0**: all five rendered
  pages contain the corrected claims, all **17 authored local file links** and
  **17 rendered local links including fragment targets** resolve. The stale
  claims are absent. `git diff --check` passed.

Remaining: M42 CI/Pages controls, then the separate M15 release review.
Blockers: none. No runtime, dependency, generated tracked artifact, commit,
push, tag, publication, or private configuration change was made for M41.

Exact next action: start a new session, read this checkpoint and the current
working tree, mark **M42 only** ◐, then implement and locally validate its
PR/main checks and Pages concurrency/locked sync. Do not start M42 here.

### M42 — pre-merge validation and controlled Pages runs

Reuse action pins and project commands for PRs and pushes to main on Python
3.12 with `contents: read`. Sync all locked extras/groups; run Ruff, Ty, pytest,
strict docs, distribution builds, and M40 wheel/sdist checks. Keep real-data
rendering in Pages; add workflow concurrency group `pages` with
`cancel-in-progress: true` and locked sync. Validate configuration locally;
remote PR checks and superseded deployment cancellation require separate push
authorization. Every unit requires `just check` and `git diff --check`.

- [x] Add PR/main Python 3.12 validation with read-only permissions and existing action pins.
- [x] Configure locked all-extras/groups sync, Ruff, Ty, pytest, strict docs, builds,
  and installed wheel/sdist model and CLI checks outside the checkout.
- [x] Add fixed `pages` workflow concurrency with cancellation and locked sync;
  retain real-data tutorial rendering in Pages.
- [x] Validate workflow configuration and shell blocks locally; pass `just check`,
  `just docs-build`, distribution smokes, and `git diff --check`.
- [x] Record evidence, remote limitations, and the separate M15 handoff.

Checkpoint — kickoff 2026-10-02: read Current focus, M41 completion evidence,
M42 scope in PROGRESS/PRD, existing workflows, project commands, and M40's
runtime-only smoke script. Preserved the pre-existing tracked diff at
`/tmp/azoic-before-m42.patch`. Context7 confirms PR/main triggers, read-only
permissions, fixed concurrency cancellation, and locked sync behavior.
Next: reuse release validation in a PR/main workflow; add Pages concurrency and
locked sync; validate locally. Remote checks/deployment cancellation and M15
remain separate. No prior milestone changes will be reverted.

Checkpoint — implementation 2026-10-02: added `.github/workflows/ci.yml`
for all pull requests and main pushes, using Python 3.12, `contents: read`, and
release workflow pins/validation commands through both installed artifact
smokes. Pages reuses the same setup pins, syncs all locked extras/groups, and
uses workflow-level `pages` concurrency with `cancel-in-progress: true`; its
real-data render/deployment stays intact. AGENTS now records workflow roles.
The installed actionlint 1.7.12 binary validates all three workflows; locked sync
passed. Builds passed; full `just check` and strict docs are running. Next:
check workflow contracts/shell blocks and execute wheel/sdist smokes, then record
all exit statuses before marking green. No release workflow edits in M42.

Checkpoint — local acceptance 2026-10-02: strict docs, distribution builds,
actionlint, workflow contract assertions, and every run block's `bash -n` check
passed. Exact new CI smoke blocks passed for both 0.4.1 artifacts in Python
3.12 outside the checkout, resolving runtime dependencies independently
(pandas 3.0.6), including model behavior/import/version checks and CLI help.
The initial local run selected old ignored 0.4.0 files from `dist/` and failed
its model-score assertion. Staging only the newly built artifacts under
`/tmp/azoic-m42-built` reproduces a fresh runner without deleting prior builds;
both corrected runs exited 0. Logs are `/tmp/azoic-m42-wheel-current.log` and
`/tmp/azoic-m42-sdist-current.log`. All pre-existing diffs outside M42's allowed
workflow/documentation files remain byte-identical to the kickoff patch.
Next: wait for the running full `just check`, then record its exit/counts, run
final diff validation, and complete the handoff. M42 remains ◐ until green.

### M42 completion checkpoint — 2026-10-02

Changed: added `.github/workflows/ci.yml` for all pull requests and main pushes.
It reuses release action pins and validation steps on Python 3.12 with only
`contents: read`: locked all-extras/groups sync, Ruff, Ty, pytest, strict docs,
wheel/sdist build, and runtime-only installed model/import/version/CLI smokes
outside the checkout. Pages retains its real-data tutorial render and deployment,
reuses the pinned checkout/Python/uv actions, adds workflow-level fixed `pages`
concurrency with cancellation, and locks sync. AGENTS records these roles;
PRD marks this milestone complete. No runtime/dependency/release workflow or
tutorial source was changed in M42; earlier uncommitted work is preserved.

Acceptance evidence:

- `uv sync --locked --all-extras --all-groups` and `uv lock --check` exited **0**.
- Final `just check` exited **0**: Ruff and production Ty green; **1051 passed,
  4 upstream array-API skips, 2 expected strict-target failures**, in **244.61 s**
  on Python **3.12.7**. Log: `/tmp/azoic-m42-check.log`.
- `just docs-build` exited **0**, with no issues in strict mode.
  Log: `/tmp/azoic-m42-docs.log`.
- `uv build` exited **0**, producing the **0.4.1** wheel and sdist.
  Log: `/tmp/azoic-m42-build.log`. Its existing uv/build-backend version warning
  is non-fatal; the configured backend remains unchanged.
- Exact CI wheel and sdist smoke blocks each exited **0** in a clean temporary
  artifact workspace, with independent runtime resolution outside the checkout
  on Python **3.12**, pandas **3.0.6**. GLM/GBM behavior, installed module paths,
  metadata versions, categorical influence, and both CLI help commands pass.
  Logs: `/tmp/azoic-m42-wheel-current.log`, `/tmp/azoic-m42-sdist-current.log`.
  The earlier stale 0.4.0 local-artifact failure and correction are recorded above.
- Installed **actionlint 1.7.12** exited **0** for CI, Pages, and release workflows.
  `uv run python /tmp/azoic-m42-validate-workflows.py` exited **0**: triggers,
  permissions, Python, release-step parity, Pages concurrency/locked sync,
  retained tutorial deployment, and all shell blocks' `bash -n` checks pass.
  Final `git diff --check` passed. No tracked generated artifacts were added.

Remaining: remote PR/main checks and superseded Pages cancellation require a
separately authorized push; they are not claimed as executed local evidence.
M15 remains the separate trusted-publisher/release review. Blockers: none for
M42's local scope. No commit, push, tag, publication, or private setting change.

Exact next action: start a new session, read this checkpoint/current working
tree, and perform **M15 only**: verify publisher repository/workflow/environment
claims, prepare a validated commit, artifact hashes, and proposed `v0.4.1` tag.
Obtain the required separate authorization before push, private settings,
tagging, or publication. Stop this session after M42.

M15 stays separate: verify trusted-publisher repository/workflow/environment
claims; prepare a validated commit, artifact hashes, and proposed `v0.4.1` tag.
Private settings, tagging, and publication require separate authorization.

## Source audit remediation plan — 2026-10-01

### Scope, validation, and completion rules

Group fixes by their shared boundary rather than adding a framework per finding.
The audit covers `src`; tests provide evidence. CI/CD, tutorial/editorial review,
and publication are deferred to the separate requested review. Update affected
API/configuration text when implementing a changed contract, without expanding
that into the second review. No new dependencies, subpackages, validation base
classes, or compatibility shims.

Prefer public `sklearn.utils.validation` functions:

- `validate_data(reset=True)` records a training schema; `reset=False` checks
  subsequent input. For native categorical DataFrames, `skip_check_array=True`
  preserves the frame and checks names/counts only: it does **not** validate
  targets, weights, finiteness, or lengths. Keep CLI-required full input metadata
  and the optional exposure/outcome prediction contract; check the post-pop
  model-feature sequence explicitly where the full schema cannot represent it.
- `check_array` supplies numeric conversion and finite-value validation;
  `check_consistent_length` supplies row-count checks. A strict vector contract
  still needs `ndim == 1`: `ensure_2d=False` also accepts 2D arrays, and
  `column_or_1d` would silently flatten a column vector.
- Reuse `_pop_weight` and `_as_arrays` at their existing shared boundaries.
  Retain domain checks for exposure floors, non-negative weights/claims,
  nonzero fitting weights, outcome consistency, and segment totals. Keep native
  missing-feature handling, valid explicit weights, and zero-weight ranking
  behaviour. Do not use private sklearn validation functions.

Public API references: [validate_data](https://scikit-learn.org/stable/modules/generated/sklearn.utils.validation.validate_data.html),
[check_array](https://scikit-learn.org/stable/modules/generated/sklearn.utils.check_array.html),
and [check_consistent_length](https://scikit-learn.org/stable/modules/generated/sklearn.utils.check_consistent_length.html).
Local feasibility checks confirmed categorical preservation, reordered-feature
rejection, finite-target validation, and length checks with installed sklearn
1.9.0. M34 must align the declared minimum with `validate_data`, added in 1.6;
At planning, the `>=1.5` claim did not cover APIs already used by Azoic.

For each milestone, reproduce the defect and add the smallest regression in
existing test modules before fixing it. Run focused tests, `just check`, and
`git diff --check`; run the strict docs build if guide/API text changes and
`just demo` only if executable tutorial sources change. Record actual results,
mark ☑ only when green, update Current focus, and stop with a handoff.

Scores are estimated **complexity / effort**, each 1–5. Complexity measures
the smallest sound repair; effort includes regressions (1 = hours, 2 ≈ one
day, 3 = several days, 4 = about a week, 5 = larger work). Finding numbers refer
to the source audit, with their behaviour restated in the checklists below.

| Status | Milestone | Priority | Findings grouped | C/E |
|---|---|---|---|---|
| ☑ | M34 — estimator schema, targets, and scoring weights | P1/P2 | #1, #4, #11; public backend import and sklearn minimum | 2/2 |
| ☑ | M35 — configuration, preprocessing, and input inspection | P1/P2 | #3, #5, #12, #14; bin counts and profile URIs | 2/3 |
| ☑ | M36 — training-only tariff calibration | P1/P2 | #2, #8; distillation independence boundary | 1/2 |
| ☑ | M37 — stable tariff arithmetic and literal workbook labels | P2 | #6, #15 | 3/2 |
| ☑ | M38 — complete and unambiguous diagnostics | P2/P3 | #7, #13; zero-exposure double lift and constant quantiles | 2/2 |
| ☑ | M39 — reproducible results and comparable evaluation | P2 | #9, #10; comparison context and small logger cleanup | 2/2 |

### M34 — estimator schema, targets, and scoring weights

- [x] Reject reordered, renamed, missing, or extra model predictors in both
  wrappers' `predict` and `score`, including frequency–severity components.
  Use sklearn schema validation where applicable; retain the small post-pop
  sequence guard needed for optional special columns. Do not silently reorder.
- [x] Validate finite one-dimensional targets and lengths before GBM backend
  fitting, including DataFrame inputs; preserve the existing supported target
  families and categorical/NaN feature behaviour.
- [x] Route frequency–severity scoring weights through `_pop_weight`'s rules:
  validate weights and the popped exposure floor, and allow explicit weights
  without an exposure column. Prediction remains exposure-optional.
- [x] Use glum's public `TweedieDistribution` import; align the sklearn minimum
  with the public APIs used (at least 1.6), without a compatibility shim.

Acceptance: regressions for swapped/renamed predictors in fit-derived schemas,
NaN/inf DataFrame targets, target/weight shape and length, negative/all-zero
scoring weights, sub-day popped exposure, explicit overrides, and prediction
without special columns. Exercise native categoricals, both wrappers,
frequency–severity, pipelines, existing sklearn estimator checks, and an
isolated import/CLI smoke at the declared sklearn minimum. The audit
observed swapped-column prediction changes of 15.44 (GLM) / 11.04 (GBM), NaN
GBM labels equivalent to zero labels, and negative-exposure FSM D² above one.

### M35 — configuration, preprocessing, and input inspection

- [x] Give `DatasetSpec` `extra="forbid"`; a misspelled optional special-column
  field must fail before it can leave an outcome among default predictors.
- [x] Require configured exposure/claim-count columns during preprocessing fit
  and validate their numeric values before weighting, division, or pooling.
  Keep the documented target/y fallback and explicit unweighted operation when
  no exposure column is configured; preserve existing one-day floor rules.
- [x] Reject non-integer or below-two `max_bins`; validate fitted mapping
  override keys and finite, strictly increasing bin edges before replacing
  state. Preserve the current replacement semantics and valid group vocabularies.
- [x] Profile bool/nullable-bool columns without requesting continuous numeric
  descriptive statistics. Preserve local paths and `s3://` strings in CLI
  profiling; use a mocked loader in tests, never a network request.

Acceptance: typo `claim_count_col` raises instead of exposing claim counts as
features; missing/negative/NaN/inf exposure and invalid claim counts raise;
valid weighted mappings retain their units. Unknown override columns,
descending/NaN/inf/duplicate edges, and invalid bin counts fail without partially
replacing fitted state. Valid override round-trips, bool profiling, and exact
URI forwarding pass. The audit accepted missing weight columns and invalid
grouper exposures, produced overlapping intervals from descending edges, and
reproduced bool `KeyError: 'min'` and `s3:/` path corruption.

### M35 checkpoint — 2026-10-01, in progress

Changed: added regressions in the existing data, preprocessing, profile, and CLI
test modules; marked M35 ◐. Preserved the pre-existing M34 working-tree changes.

Verified: focused new regressions on unchanged production source: **47 failed,
11 passed, 209 deselected**. Reproduced accepted misspelled DatasetSpec fields,
missing/invalid weight columns, sub-day exposure, invalid bin counts and edges,
unknown override keys, partially replaced grouper state, bool profiling failure,
and local/S3 path alteration. Existing positive cases cover replacement semantics,
target fallback, and exposure units. No network calls in the URI regressions.

Remaining: production fixes, affected contract docs, focused/full checks, strict
docs build, and final handoff. Blockers: none; the sandbox wrapper intermittently
fails before commands launch, so local reads/checks use approved escalation.
Next action: implement shared column validation and atomic mapping replacement,
then the small DatasetSpec/profile/CLI fixes. Do not start M36.

### M35 checkpoint — 2026-10-01, implementation validated locally

Changed: DatasetSpec forbids extra fields. Both preprocessors use their shared
column reader to require configured exposure/claim-count columns and validate
finite 1D numeric values, non-negative counts, and the existing tolerant one-day
exposure floor before arithmetic. Binner target resolution reuses validated
exposure. Bin counts reject floats, booleans, and values below two. Mapping
overrides check fitted columns and build edges/vocabularies locally before
replacing state; omitted columns still pass through. Boolean profiling uses
discrete stats; CLI profiling forwards strings unchanged. Updated affected API,
guide, configuration reference, actuarial engineering rule, and PRD scope text.

Verified: affected modules (`tests/test_data.py`, `tests/test_preprocessing.py`,
`tests/test_profile.py`, `tests/test_cli.py`) passed **265 tests, 2 upstream
array-API skips**. This includes all 58 new cases and existing transformer
estimator checks, weighted mappings, pipelines, override round-trips, and CLI
local-file smoke tests. Ruff and production Ty checks passed.

Remaining: full `just check`, strict documentation build (running), format/diff
checks, and completion handoff. Blockers: none. No tutorial sources changed.
Next action: finish those checks, mark M35 ☑ only when green, set M36 as the next
milestone, and stop without beginning it.

### M35 completion checkpoint — 2026-10-01

Changed: completed all four M35 checklist items and the affected contract docs.
The implementation uses the existing column reader and public sklearn checks;
mapping overrides validate completely before replacing fitted mappings and
vocabularies. Preserved the pre-existing M34 changes. No dependencies, modules,
generated artifacts, or compatibility shims were added.

Verified:

- The 58 new synthetic regression cases first yielded **47 failures and 11
  passes** on unchanged production source. All now pass, covering misspelled
  configuration, missing/negative/non-finite/non-numeric weight columns, sub-day
  exposure and day-count tolerance, invalid bin counts/edges/keys, unchanged
  state after invalid overrides, replacement semantics, target fallback, rate
  units, boolean profiling, and exact mocked local/S3 path forwarding.
- Affected data/preprocessing/profile/CLI modules: **265 passed, 2 upstream
  array-API skips**, including transformer estimator checks and pipeline tests.
- Final `just check`: Ruff and production Ty green; **932 passed, 4 upstream
  array-API skips, 2 expected strict-target failures** in 563.68 seconds.
- `just docs-build` passed strict mode. Ruff format check for all eight changed
  source/test files and `git diff --check` passed. No tutorial sources changed,
  so `just demo` was not required; the full gate includes tutorial smoke tests.

Remaining: M36–M39 and the separately scoped CI/CD/documentation/tutorial review.
The previously recorded pandas 3 compatibility issue remains outside this
milestone. Blockers for M35: none.
Next action: in a new implementation session, reproduce M36's holdout leakage
and two-dimensional recalibration outcome failures; mark only M36 ◐, implement
training-only CLI recalibration and vector validation, validate direct/distilled
exports and independence documentation, then stop after its green handoff.
Stop this session with M35 ☑; do not begin M36.

### M36 — training-only tariff calibration

- [x] CLI export recalibrates from `Run.train_indices` only, for direct GLMs
  and distilled students. Keep the fitted estimator and existing holdout for
  evaluation/fidelity; `--no-recalibrate` remains the structural export.
- [x] Validate one-dimensional recalibration outcomes and matching frame length
  with public array/length checks before deriving observed totals. Direct
  `export_tariff` callers still choose their calibration frame explicitly.
- [x] State that the distillation object-identity guard is not proof of row
  independence. Keep the CLI's stored partitions and test them; direct callers
  must supply disjoint observations. Add no speculative row-identity API.

Acceptance: changing only held-out outcomes cannot change exported rates,
training calibration factors, or the distilled student's fitted predictions.
Workbook rates reproduce training totals and structural exports stay unchanged.
Two-dimensional outcomes raise rather than summing extra columns. The audit's
holdout-only loss change multiplied the CLI base by 2.85 with identical training
predictions; a two-column outcome array changed an export base from 1.00049 to
27.68014. Cover direct and distilled CLI exports and the changed-data guard.

### M36 checkpoint — 2026-10-01, in progress

Changed: marked M36 ◐ and added synthetic regressions in the existing tariff
and CLI test modules. Preserved the M34/M35 working-tree changes. Extended the
changed-input guard coverage to direct GLM exports as well as distilled GBMs.

Verified: `uv run pytest -q tests/test_tariff.py tests/test_cli.py -k
'rejects_2d_outcomes or ignores_holdout_outcomes'` on unchanged production source
reported **6 failed, 2 passed, 64 deselected**. Four accepted 2D ndarray/DataFrame
outcome cases failed to raise. Changing only holdout losses multiplied both
direct and distilled workbook bases by about **2.56**, with identical fitted
predictions. Both structural exports already passed, including workbook rate
reproduction. Tests use non-positional index labels and a returned split seed
different from the YAML seed to enforce stored positional partition reuse.

Remaining: production fixes, affected contract documentation, focused/full
checks, strict docs build, and handoff. Blockers: none. The sandbox wrapper
intermittently fails before launching; an approved local read bypass succeeded.
Next action: slice calibration inputs using `Run.train_indices`, validate outcome
vectors with public sklearn checks, and document the distillation independence
boundary. Do not start M37.

### M36 checkpoint — 2026-10-01, implementation validated locally

Changed: CLI calibration reuses `Run.train_indices` for both direct GLMs and
distilled students; fitting and fidelity retain the existing training/test
partitions. Tariff export validates finite numeric outcomes with public
`check_array`, rejects non-vector shapes, and checks frame length with
`check_consistent_length` before summing observed claims. Negative claims and
the exposure floor remain guarded. Updated CLI help, API docstrings, operations
guide, configuration reference, and the tutorial's repeated calibration prose.
The distillation identity guard is explicitly not a row-independence guarantee;
direct callers remain responsible for disjoint observations. No new API or
dependency was added.

Verified: `uv run pytest -q tests/test_tariff.py tests/test_cli.py` passed
**72 tests**, including all eight new defect regressions and direct/distilled
changed-input guards. Workbooks reproduce fitted rates and training totals;
training factors and student predictions are invariant to holdout loss changes.
Structural exports remain at the original scale. Ruff format passed for all
four affected Python files. Initial Ruff and diff checks passed.

Remaining: final `just check`, strict docs build, completion status and handoff.
Blockers: none. No executable tutorial cells or configuration changed, so M36's
acceptance does not require a real-data render. Next action: complete the full
gate and documentation build, mark M36 ☑ only when green, then hand off M37.

### M36 checkpoint — 2026-10-01, completed

Changed: completed all three M36 checklist items. Direct and distilled CLI
exports calibrate only on stored training positions. Public sklearn array and
length checks reject invalid recalibration outcomes before total calculation;
direct library callers retain explicit frame selection. Documented that distinct
distillation frame objects do not prove disjoint observations. Updated affected
help/API/guide/reference text and the tutorial's repeated prose only. Preserved
the existing M34/M35 changes; no dependencies, new APIs, modules, compatibility
shims, or generated artifacts were added.

Verified:

- The eight new synthetic defect cases first reported **6 failures and 2
  passes** against unchanged production source. All now pass. They cover
  one-/two-column ndarray and DataFrame outcomes, direct/distilled calibration,
  unchanged structural exports, and holdout-loss invariance of workbook rates,
  training factors, fitted student predictions, and fidelity metadata.
- `uv run pytest -q tests/test_tariff.py tests/test_cli.py`: **72 passed**.
  Existing library exports still balance their explicitly chosen frame. New
  CLI checks apply saved workbook factors, reconcile training claim totals,
  use non-positional labels and the returned run's actual split, and extend
  changed-dataset rejection to direct GLMs as well as distilled students.
- Final `just check`: Ruff/Ty green, **942 passed, 4 upstream array-API skips,
  2 expected strict-target failures** in 189.38 seconds. The gate includes
  pipeline, estimator, distillation, tuning, workflow, and tutorial smoke tests.
- `just docs-build` passed strict mode. Ruff format check for the four affected
  Python files and `git diff --check` passed. A comparison with HEAD confirmed
  every tutorial fenced code/configuration block is unchanged; the prose-only
  correction required no real-data render under this plan's acceptance rules.

Remaining: M37–M39 and the separately scoped CI/CD/documentation/tutorial review.
Blockers for M36: none. Direct callers still own fit/validation observation
independence; M36 deliberately adds no row-identity API.
Next action: in a new implementation session, reproduce M37's unstable tariff
arithmetic and Excel formula-like label defects, mark only M37 ◐, and implement
its stable arithmetic and literal workbook text requirements. Stop here with
M36 ☑; do not begin M37.

### M37 — stable tariff arithmetic and literal workbook labels

- [x] Sum the linear predictor before exponentiating in tariff application;
  fold categorical reference coefficients into the intercept before computing
  the structural base. Reject non-finite/unrepresentable extracted factors,
  workbook factors, and final rates instead of returning NaN/inf silently.
  Preserve a legitimately zero base from zero observed-total recalibration.
- [x] Use the installed openpyxl writer's literal string cell handling for
  user-provided feature/level/reference/mapping text. Preserve typed numeric
  and boolean labels; do not escape by changing the label's value.

Acceptance: coefficient 1000 at x=0.001 produces e, cancelling large terms
produce one, and accepted tariffs agree with GLM predictions. Unrepresentable
workbook factors fail clearly; existing typed-level, reference, recalibration,
and three-sheet round-trips pass. A category `=1+1` stays that exact string
with Excel string cell type rather than becoming a formula. This takes ownership
of M33's deferred tariff-overflow observation.

### M37 checkpoint — 2026-10-01, in progress

Changed: added synthetic regressions in the existing tariff test module and
marked M37 ◐. Preserved the completed M34–M36 working-tree changes.

Verified: the final new-case reproduction reported **29 failures and 1 pass**
against unchanged production source. Arithmetic cases reproduce coefficient-exponentiation overflow,
lost cancellation, invalid coefficients/factors/rates, and recalibration
overflow/underflow. Literal-label cases cover direct and pipeline exports;
zero-observed-total recalibration remains a preservation check. Corrected test
setup to use varying GLM targets and the existing grouper's public parameters.

Remaining: implement log-space arithmetic and literal string cells, update
affected API/guide text, run focused tests, `just check`, strict docs build, and
diff checks. Blockers: none; shell checks use the approved sandbox fallback
after `bwrap` failed to initialize loopback networking.
Next action: repair the shared tariff extraction/application/export boundaries
and finish only M37. Do not start M38.

### M37 checkpoint — 2026-10-01, implementation validated locally

Changed: tariff application now sums the linear predictor before exponentiating;
extraction folds categorical reference coefficients into the intercept first.
Shared exponentiation checks reject overflow, underflow to zero, and non-finite
results. Numeric coefficients stay in log space until application; export also
checks representability of per-unit factors. Recalibration uses log arithmetic
and preserves a zero base for zero observed claims. Workbook strings use the
installed openpyxl writer's string cell type without changing values; typed
numeric and boolean levels remain intact. Updated affected API and guide text.

Verified: `uv run pytest -q tests/test_tariff.py tests/test_cli.py` passed
**102 tests**, including all **30 new cases**, existing reference/typed-level
and three-sheet round-trips, distillation, and training-only recalibration.
Focused Ruff checks, formatting, and `git diff --check` passed.

Remaining: full `just check` and strict `just docs-build`, then final review and
completion handoff. Blockers: none. Tutorial executable sources are unchanged;
no manual real-data render is required. Next action: finish the full gates and
mark only M37 ☑ when green; do not start M38.

### M37 completion checkpoint — 2026-10-01

Changed: completed both M37 checklist items. Tariffs sum log contributions
before exponentiating, including categorical reference folding and total
recalibration. Invalid coefficients/base/factors and overflow or underflow to
zero raise clearly; zero observed-total recalibration remains valid. Numeric
coefficients can be applied when their per-unit workbook factors cannot be
represented; those exports fail before opening the output file. Workbook text
uses literal string cells without altered labels, preserving numeric/boolean
types and the three-sheet schema. Updated API/guide contracts and PRD status.
Preserved all pre-existing M34–M36 changes; no dependencies or generated
artifacts were added.

Verified:

- The final **30 new synthetic cases** first reported **29 failures and 1
  preservation pass** against unchanged production source. All now pass.
  Coefficient 1000 at x=0.001 yields e; cancelling large numeric terms yield
  one; cancelling intercept/reference coefficients agree with GLM predictions.
  Checks cover non-finite parameters, unrepresentable base/categorical/per-unit
  factors and rates, stable extreme-total recalibration, and its output guards.
- `uv run pytest -q tests/test_tariff.py tests/test_cli.py`: **102 passed**.
  Existing references, typed ordered levels, structural/recalibrated workbook
  round-trips, pipeline mappings, distillation, and training-only exports pass.
  Direct/pipeline workbook inspection verifies `=1+1`, formula-like feature and
  mapping text, and `#N/A` remain literal strings; numbers and booleans retain
  their cell types. Zero observed claims still yield zero applied rates, with
  unknown-category validation preserved.
- Final `just check` exited successfully: Ruff/Ty green, **972 passed,
  4 upstream array-API skips, 2 expected strict-target failures**, in 177.37
  seconds. `just docs-build` passed strict mode with no issues. Focused Ruff
  format checks and `git diff --check` passed.
- Executable tutorial sources are unchanged, so no real-data render was
  required. Working-tree status contains no new generated files.

Remaining: M38–M39 and the separate CI/CD/documentation/tutorial review.
Blockers for M37: none. Next action: in a new implementation session, reproduce
M38's plot-validation, double-lift grouping, and constant-quantile failures;
mark only M38 ◐ and implement its acceptance checks. Stop here with M37 ☑;
do not begin M38.

### M38 — complete and unambiguous diagnostics

- [x] Extend existing `_as_arrays` with public finite-array and length checks
  instead of adding a second validation layer; retain strict vector and
  actuarial sign rules. Reuse it for actual-versus-predicted plots and remove
  the separate flattening helper. Require positive exposure for rate division.
- [x] Validate double-lift generated column names against each other and
  reserved outputs before aggregation; reject degenerate segment exposure using
  the existing calibration/one-way threshold. Ranking curves retain zero weights.
- [x] Give constant unweighted predictions one real quantile group while
  preserving supplied missing group labels as a distinct segment. Reuse
  `make_strata` for diagnostic quantiles; do not change weighted tie semantics.

Acceptance: `label_a="observed"` cannot overwrite observed rates and equal
model labels raise; zero-exposure double-lift groups fail clearly. Invalid
plotting values raise even with explicit axis limits, and valid charts retain
all input exposure/claims. Constant prediction tables preserve totals with an
ordinary group label. The audit replaced observed 15 by predicted 1.5 through a
label collision and plotted exposure 2 of 3 with a NaN prediction. This takes
ownership of M33's deferred constant-qcut observation.

### M38 checkpoint — 2026-10-01, in progress

Changed: added regressions in the existing metrics, plots, and validation test
modules; marked only M38 ◐. Preserved the pre-existing M34–M37 changes.

Verified: the 44 new synthetic cases against unchanged production code reported
**34 failed, 10 passed, 218 deselected**. Reproduced colliding double-lift labels,
zero/sub-day segment exposure, unweighted constant predictions labelled missing,
accepted non-finite/negative plotting inputs, malformed vectors, and flattened
DataFrames. Positive density-total and zero-weight preservation cases passed.
Context7 confirmed public sklearn array/length checks and Matplotlib hexbin
exposure aggregation. No network or real-data calls in tests.

Remaining: production fixes, affected contract documentation, focused tests,
`just check`, strict docs build, diff checks, and final handoff. Blockers: none;
the sandbox wrapper intermittently fails before launch, so checks use approved
escalation. Next action: reuse `_as_arrays` for plotting, guard generated
double-lift columns and segment totals, and fix constant strata in `make_strata`.
Do not start M39.

### M38 checkpoint — 2026-10-01, implementation validated locally

Changed: `_as_arrays` uses public `check_array` and `check_consistent_length`
with strict vectors and existing sign guards. Actual-versus-predicted plots
reuse it, require positive exposure, and no longer flatten DataFrames. Double
lift checks generated names before aggregation and rejects segment exposure
below the existing one-day threshold. Calibration reuses `make_strata`, whose
unweighted constant observations receive group 0 while missing rows keep -1;
weighted ties remain unchanged. Updated docstrings and the diagnostics guide.

Verified: `uv run pytest -q tests/test_metrics.py tests/test_plots.py
tests/test_validation.py --tb=short`: **262 passed** in 16.95 seconds. Shared
finite/length checks emit sklearn's native errors, so existing tests now accept
those messages. Corrected the sub-day fixture to put its low-weight observation
in a distinct weighted quantile; a low-weight row absorbed into a valid segment
must remain legal. Focused Ruff lint and format checks passed before this small
fixture correction. Density tests reconcile all claims and exposure in both
panels, including zero claims and pandas Series; supplied missing groups and
weighted quantile behavior stay green.

Remaining: full `just check`, strict docs build, final format/diff checks, and
completion handoff. No dependencies, tutorial source changes, or generated
artifacts added. Blockers: none. Next action: finish those gates, mark only M38
☑ when green, and set M39 as next for a separate implementation session.

### M38 completion checkpoint — 2026-10-01

Changed: completed all three M38 checklist items. Metrics and
actual-versus-predicted plots share public array/length validation with strict
vectors and existing sign rules; plotting requires positive exposure before
rate division. Removed the flattening helper. Double-lift model columns cannot
collide with each other or reserved outputs, and segment exposure uses the
same one-day threshold as calibration/one-way tables. Unweighted constant
predictions have group 0 through `make_strata`; supplied missing groups and
weighted ties retain their meaning. Updated API docstrings, the diagnostics
guide, and PRD status. Preserved all pre-existing M34–M37 work.

Verified:

- The initial 44 new synthetic cases reproduced **34 failures and 10
  preservation passes** against unchanged production source. All final cases
  pass, covering NaN/inf with explicit axis limits, negative claims/exposure,
  zero exposure, scalar/column/DataFrame and mismatched inputs, generated-column
  collisions, zero/sub-day segments, and constant quantiles with missing rows.
- `uv run pytest -q tests/test_metrics.py tests/test_plots.py
  tests/test_validation.py --tb=short`: **262 passed** in 16.95 seconds.
  Density totals reconcile exposure and claims in both panels; pandas Series,
  exact-zero claims/predictions, supplied missing segments, weighted boundaries,
  zero-weight ranking curves, and valid double-lift segments remain supported.
- Final `just check` exited successfully: Ruff/Ty green, **1016 passed,
  4 upstream array-API skips, 2 expected strict-target failures**, in 187.86
  seconds. `just docs-build` passed strict mode with no issues. Ruff format
  checks for all six changed source/test files and `git diff --check` passed.
- No executable tutorial sources changed in M38, so no real-data render was
  required; the full gate includes the tutorial smoke tests. No dependencies
  or generated files were added.

Remaining: M39 and the separate CI/CD/documentation/tutorial review. Blockers
for M38: none. Next action: in a new implementation session, reproduce M39's
categorical-fingerprint, configuration-snapshot, and comparison-context defects;
mark only M39 ◐, implement its checklist and logger cleanup, run its acceptance
checks, then stop after a green handoff. Stop here with M38 ☑; do not begin M39.

### M39 — reproducible results and comparable evaluation

- [x] Extend `_data_fingerprint` with categorical vocabulary (including unused
  levels and its dtype), declared order, and the ordered flag, using existing
  pandas hashing. Changed fingerprints are intentional; old runs need fresh
  evaluation rather than a compatibility path.
- [x] Deep-copy the configuration and recorded parameter containers when
  constructing a run so caller mutations cannot rewrite its history. Do not
  add a deep-freeze framework or promise that public dicts/DataFrames are immutable.
- [x] Warn once when a comparison mixes dataset fingerprints, target/exposure
  definitions, or holdout membership. Compare positions as sets, since row order
  does not change the evaluated sample. Keep the table schema and permit
  intentionally descriptive comparisons; make the warning name the affected runs.
- [x] Simplify logger parameter conversion with a comprehension and finite
  metric filtering with `math.isfinite`; preserve existing logged values.

Acceptance: category-order/vocabulary/dtype/ordered-flag changes alter the
fingerprint even when observed cell values match; an unchanged frame matches.
Mutating the caller's config and nested params leaves the recorded run intact.
Matched comparisons are warning-free; unmatched comparisons warn without losing
rows; permutation of the same holdout membership is accepted. Logger tests stay
green. The audit changed grouping membership without changing the fingerprint
and rewrote a historical run's family by mutating its source configuration.

### M39 checkpoint — 2026-10-01, in progress

Changed: added synthetic regressions in the existing workflow/reporting modules,
extended logger coverage, and marked only M39 ◐. Preserved M34–M38 changes.

Verified: targeted regressions on unchanged production source: **16 failed,
3 passed, 89 deselected**. Categorical order, unused vocabulary, category dtype,
and ordered flag leave the fingerprint unchanged; caller config and nested
dict/list parameters rewrite recorded history; mixed comparison contexts emit
no warning. Holdout permutations and logger preservation cases pass.

Remaining: shared-boundary fixes, affected API/guide text, focused tests,
`just check`, strict docs build, format/diff checks, and completion handoff.
Blockers: none. The sandbox wrapper intermittently fails before launch; local
reads/checks use approved escalation. Next action: implement M39 without adding
dependencies, a deep-freeze framework, or fingerprint compatibility handling.

### M39 checkpoint — 2026-10-01, implementation validated locally

Changed: fingerprints hash categorical vocabularies plus column position,
category dtype/order, unused levels, and the ordered flag. Shared evaluation
deep-copies config and recorded nested parameters. Comparison tables warn once
with the baseline and mismatched run names for different fingerprint,
target/exposure definitions, or holdout membership; generators, rows, columns,
and metrics are preserved, and holdout permutations do not warn. Dashboards
and CLI reuse that boundary. Logger conversion uses a comprehension and finite
filtering uses `math.isfinite`. Corrected misleading result immutability text
and updated affected guide/API/configuration/PRD contracts.

Verified: `uv run pytest -q tests/test_workflow.py tests/test_reporting.py
tests/test_mlops.py tests/test_tune.py tests/test_cli.py --tb=short`:
**158 passed** in 63.28 seconds. Ruff and production Ty checks passed;
`git diff --check` passed. `just docs-build` passed strict mode with no issues.

Remaining: final `just check`, format/diff review, and completion handoff.
Blockers: none. No tutorial sources, dependencies, or generated files added.
Next action: finish the full gate, mark M39 ☑ only when green, and stop;
the separate CI/CD/documentation/tutorial review remains outside this milestone.

### M39 completion checkpoint — 2026-10-01

Changed: completed all four M39 checklist items. Dataset fingerprints include
categorical vocabulary, unused levels, category dtype, declared order, and the
ordered flag. Workflow and tuning share configuration/parameter snapshotting.
Tables, dashboards, and CLI comparisons share one warning for incompatible
evaluation contexts, retaining every metric row and accepting holdout
permutations. Logger cleanup preserves parameter strings and finite metrics.
Updated affected contract docs and PRD status; preserved all M34–M38 work.
No dependencies, modules, compatibility paths, or generated files were added.

Verified:

- The final targeted reproduction first produced **16 failures and 3
  preservation passes** on unchanged production source. All cases now pass,
  covering category order/vocabulary/dtype/ordered flag, unchanged frames,
  config and nested dict/list parameter mutation, mixed fingerprint/target/
  exposure/holdout contexts, one warning naming affected runs, retained table
  schema and metrics, generator inputs, holdout permutations, and dashboard
  warnings. Logger coverage preserves None/container strings, zero/negative
  finite metrics, and filtering of NaN and both infinities.
- Focused workflow/reporting/MLflow/tuning/CLI checks: **158 passed** in
  63.28 seconds, including fitted estimator return, tuning's outer partition,
  model cards, optional integrations, and existing CLI smoke tests.
- Final `just check`: Ruff and production Ty green; **1034 passed,
  4 upstream array-API skips, 2 expected strict-target failures**, in 194.62
  seconds. `just docs-build` passed strict mode with no issues. Ruff format
  checks for all six M39 source/test files and `git diff --check` passed.
- No tutorial source changed in M39, so no real-data render was required;
  the full gate includes the synthetic tutorial integration tests.

Remaining: no M39 work. Public dictionaries/DataFrames remain mutable; old
category-bearing runs need fresh evaluation rather than fingerprint migration.
The separate CI/CD/documentation/tutorial review and M15 release review remain.
Blockers for M39: none. Next action: start that separate review when requested,
then assess M15 readiness; publication requires its own authorization.
Stop this session with M39 ☑; do not begin the separate review or M15.

### Planning checkpoint — 2026-10-01

Changed: recorded M34–M39 as pending, replaced stale Current focus instructions,
and mirrored the plan in PRD/AGENTS. M33's completed evidence remains historical;
its mapping, overflow, constant-quantile, and distillation observations now have
explicit owners. The small native cleanups stay within the related milestones.
Verified: source audit baseline `just check` (839 passed, 4 upstream skips);
fresh native-validation feasibility probe; official sklearn API documentation
and installed implementation inspected. After this Markdown update, fresh
`just check` passed Ruff, Ty, and **839 tests with 4 upstream skips**;
milestone consistency and the local plan-link target passed; `git diff --check`
passed. Only AGENTS.md, PRD.md, and PROGRESS.md changed.
Remaining: all six implementation milestones and the separate CI/CD,
documentation, and tutorial review. Nothing has been implemented by this update.
Blockers: none.
Next action: in the next implementation session, reproduce M34 and mark only
M34 ◐ before editing production code.

### M34 checkpoint — 2026-10-01, in progress

Changed: added synthetic regressions in `tests/test_models.py`; marked M34 ◐.
Verified: before production edits, `uv run pytest tests/test_models.py -k m34
-q --tb=short` produced **30 failures, 2 passes**. Predictor changes were
accepted, invalid targets reached backend construction, GBM accepted column
weights, and FSM scoring accepted invalid exposure and could not use explicit
weights without exposure. Native categorical/NaN-feature control passed.
Public sklearn validation documentation and the installed glum public import
were checked. sklearn's column-vector target conformance check conflicts with
the required strict-vector contract; record only that check as an expected
failure for each wrapper, with a direct regression enforcing rejection.
Remaining: implementation, focused/full checks, docs build, and isolated
sklearn-minimum import/CLI smoke. Blockers: none.
Next action: fix the shared estimator boundaries, preserving full public fit
metadata and optional special columns.

### M34 checkpoint — 2026-10-01, implementation validated locally

Changed: public `validate_data` records full fit metadata and checks ordinary
schemas; one post-pop sequence guard covers optional special columns. Shared
target and weight boundaries now reject non-finite values, column vectors, and
mismatched lengths. FSM scoring uses `_pop_weight`, preserving explicit-weight
overrides and exposure-free predictions. Switched to the public glum import;
raised the sklearn minimum to 1.6 in package/lock metadata and documented the
input contract. Existing audit-plan edits were preserved.
Verified: `uv run pytest tests/test_models.py -x -q --tb=short` passed **278
tests, 2 upstream skips, 2 expected column-vector contract failures**. Added
GBM-component FSM coverage and scoring-target regressions afterward; their
final checks are running. `uv sync --all-extras --all-groups --locked` passed;
strict `just docs-build` passed. Full `just check` has passed Ruff and Ty and
is running pytest. `git diff --check` passed. The isolated runtime installation
with `scikit-learn==1.6.0` succeeded.
Remaining: final full-suite results, isolated minimum-version import/CLI and
estimator results, final diff review, and completion handoff. Blockers: none.
Next action: finish acceptance checks, then mark only M34 complete.

Minimum-version investigation: the installed wheel imported and the isolated
CLI `--help` passed with sklearn 1.6.0. A broader estimator run initially had
36 failures / 247 passes / 2 expected failures: the unconstrained installer
selected pandas 3.0.6, which changes default string dtype and NumPy writeability.
This is independent of sklearn and outside M34; leave pandas 3 support for a
separate decision. Rerun with the repository's locked pandas 2.3.3 to isolate
the declared sklearn minimum. No pandas compatibility code or dependency cap
has been added.

Verified after isolating pandas: the installed-wheel estimator suite on
sklearn 1.6.0 / pandas 2.3.3 passed **283 tests, 2 expected column-vector
contract failures**. The import and CLI smoke passed, including the public
glum distribution import. M34 checklist items are implemented and their
focused acceptance checks pass; retain ◐ until the final full suite is green.

### M34 completion checkpoint — 2026-10-01

Changed: completed all four M34 checklist items. Predictor schemas are checked
in both wrappers and FSM, including GLM/GBM components and pipelines. Full fit
metadata remains available to the CLI, and prediction accepts omitted special
columns. Targets and weights reject invalid shapes, lengths, and values before
backend use. FSM scoring validates exposure and supports explicit overrides
without exposure. Public glum import, sklearn >=1.6 package/lock declarations,
and API/installation/engineering contract text are updated.

Verified:

- New regressions first failed **30 cases** on the original production source;
  the final suite includes **37 M34 cases**, covering ordinary/post-pop schemas,
  optional specials, native categories and NaN features, target/weight shape
  and length, non-finite targets, invalid scoring weights, exposure floors,
  explicit overrides, both component backends, and pipelines.
- `uv sync --all-extras --all-groups --locked` and final `just check` passed:
  Ruff/Ty green, **874 passed, 4 upstream array-API skips, 2 expected failures**.
  The two expected failures are sklearn's column-vector flattening check;
  strict 1D target rejection is intentional, documented, and directly tested.
- `just docs-build` passed strict mode. `uv run ruff format --check
  src/azoic/models.py tests/test_models.py`, `uv lock --check`,
  `uv run azoic --help`, and `git diff --check` passed.
- A fresh installed wheel in `/tmp/azoic-m34-sklearn16` imported Azoic and the
  public glum distribution, and its CLI `--help` passed with sklearn **1.6.0**.
  Its complete estimator test module passed **283 tests, 2 expected failures**
  with the repository's locked pandas **2.3.3**.
- No tutorial sources changed; `just demo` was not required. No dependencies,
  generated artifacts, subpackages, or compatibility shims were added.

Remaining: M35–M39, separate CI/CD/documentation/tutorial review, and the
independently observed pandas 3 string-dtype/writeability compatibility issue.
The unconstrained minimum-environment failure and controlled rerun are recorded
above; M34 does not claim pandas 3 compatibility. Blockers for M34: none.
Next action: in a new implementation session, reproduce M35's configuration,
preprocessing, mapping, boolean-profile, and URI failures; mark only M35 ◐,
then implement and validate its checklist. Stop this session with M34 ☑.

## Fail-closed hardening plan — 2026-09-14

### Scope and completion rules

Library-only fixes. No public API additions, no new dependencies, no behaviour
change for valid inputs, no tutorial changes (no `just demo` required).
Decisions locked at planning: freq-sev component families **warn only**;
`RiskGBM.score` **raises** with a `scoring=` pointer for unmapped objectives;
`ModelSpec.build` **raises** on an `exposure_col` contradicting
`spec.exposure`; recorded params come from one `effective_params` source.

For every milestone:

1. Update its status to ◐ and record the starting checkpoint. Complete only its
   scope; incidental findings go in the checkpoint for a later decision.
2. For each fixed reproduction, add the smallest synthetic regression that
   would catch it. Reuse existing fixtures; no prose snapshots.
3. Run focused tests, `just check`, and `git diff --check`.
4. Record commands, results, and limitations in the checkpoint. Mark ☑ only
   when green, advance **Current focus**, and stop. If interrupted, retain ◐
   and give the exact remaining action.

| Status | Milestone | Findings addressed |
|---|---|---|
| ☑ | M31 — diagnostics and exposure weighting | #1 non-finite diagnostics corruption; #2 silent loss of exposure weighting |
| ☑ | M32 — configuration, labels, scoring, recorded params | #3 spec aliasing; #4 preprocessing fail-open; #5 freq-sev components/clipping; #6 label collisions; #7 unrelated score; #8 param drift |

### M31 — diagnostics and exposure weighting

- [x] `metrics._as_arrays` validates: `y_true` finite non-negative, `y_pred`
  finite (sign-permissive; Poisson GBM zeros are legitimate), `sample_weight`
  finite non-negative, one-dimensional, equal length. Messages mirror
  `stability_table`'s wording.
- [x] `double_lift_table` validates `pred_b` identically; `calibration_table`
  validates `claim_count` finite non-negative when provided.
- [x] `_pop_weight(..., require_exposure=True)` in `RiskGLM.fit/score` and
  `RiskGBM.fit/score` raises when `exposure_col` is set but absent from X (or
  X is not a DataFrame). `predict` keeps `require_exposure=False`.
- [x] Regressions: the reported three-row double-lift case (1,030 claims)
  raises instead of returning 30; NaN/inf/negative payloads raise across
  gini/lorenz/op_ratio/calibration/one_way/double_lift; unweighted fit/score
  with a missing configured exposure column raises; predict without the
  column still works; estimator checks stay green.

Checkpoint: 2026-09-14 — in progress
Changed: recorded M31/M32 in PRD.md section 6 and this plan; marked M31 ◐.
Verified: all eight findings reproduced read-only against the M25–M30 baseline
(three-row double lift returned 30 of 1,030 claims; missing-column GLM fit
succeeded unweighted; spec aliasing, strategy/column typos, `group_0` and
`"nan"` collisions, `regression_l1` score fallback raising on non-positive
predictions, and fitted-vs-recorded `exposure_col` drift all confirmed).
`parametrize_with_checks` uses default-param instances, so the new raises stay
check-green; `distill_gbm` validates exposure presence itself; no test relies
on silent column-dropping.
Remaining: both fixes, regressions, focused tests, `just check`, diff check.
Blockers: none.
Next action: implement `_as_arrays` validation in `src/azoic/metrics.py`.

Checkpoint: 2026-09-14 — complete
Changed: `src/azoic/metrics.py` (`_as_arrays` validation; `double_lift_table`
pred_b check; `calibration_table` claim_count check); `src/azoic/models.py`
(`_pop_weight` gains `require_exposure`; fit/score of RiskGLM/RiskGBM pass it);
`tests/test_metrics.py` (+70 parametrized regressions; the existing
`test_diagnostic_quantiles_ignore_missing_exposure` codified the old silent
drop for calibration/double_lift and was updated to assert the raise -- its
one_way missing-*feature* path is unchanged); `tests/test_models.py` (+4
regressions incl. the freq-sev sub-estimator exposure-col side effect);
PRD.md section 6 + this plan recorded.
Verified: focused `pytest tests/test_metrics.py tests/test_models.py` 352
passed; `just check` Ruff/Ty green, **764 passed, 4 upstream skips** (baseline
690); `git diff --check` clean; both P1 reproductions now raise
("y_pred must contain only finite predictions",
"exposure_col 'exposure' not found in X ...") and predict without the exposure
column still works. Estimator checks green (default-param instances).
Remaining: none for M31. M32 untouched.
Blockers: none.
Next action: start M32 in a new session (DatasetSpec distinctness first).

### M32 — configuration, labels, scoring, recorded params

- [x] `DatasetSpec` requires distinct names across target/exposure/
  claim_count/time_col.
- [x] `AutoBinner`/`AutoGrouper` raise on unknown requested `cols` and unknown
  `strategy`; similarity grouping without a target raises (estimator checks
  stayed green -- sklearn's transformer checks pass `y`, so no downgrade to
  UserWarning was needed).
- [x] `ModelSpec` warns on ill-posed frequency/severity families;
  `FrequencySeverityModel.predict` warns when clipping negatives.
- [x] `AutoGrouper` synthetic labels namespaced against real levels;
  `one_way_table` keeps genuine `"nan"` distinct from missing.
- [x] `RiskGBM.score` raises with a `scoring=` pointer for unmapped
  objectives; L2 aliases map to power 0.
- [x] `ModelSpec.build` raises on contradictory `exposure_col`;
  `effective_params` is the single source for build and recorded params.

Checkpoint: 2026-09-14 — in progress
Changed: marked M32 ◐; no code edits yet.
Verified: M31 completion checkpoint (764 tests green) is the baseline; the six
M32 reproductions were confirmed read-only in the review session.
Remaining: all six fixes, regressions, focused tests, `just check`, diff check.
Blockers: none.
Next action: DatasetSpec distinctness validator in `src/azoic/data.py`.

Checkpoint: 2026-09-14 — complete
Changed: `src/azoic/data.py` (special-column distinctness validator);
`src/azoic/preprocessing.py` (unknown-cols and unknown-strategy raises in both
classes, similarity-requires-target raise, synthetic-label namespacing via a
`taken` set with suffix bumping); `src/azoic/metrics.py` (`one_way_table`
keeps true NA as the level key so genuine `"nan"` strings stay distinct);
`src/azoic/models.py` (`_GBM_OBJECTIVE_POWER` extended with L2 aliases,
unmapped objectives raise with a `scoring=` pointer, `FrequencySeverityModel.predict`
warns on actual clipping); `src/azoic/workflow.py` (`ModelSpec` warns on
negative-support freq/sev families, `effective_params` is the single source
for `build` and `ModelResult.params`, contradictory `exposure_col` raises).
Tests: +28 regressions across test_data/test_preprocessing/test_metrics/
test_models/test_workflow. Four pre-existing tests codified target-less
similarity fits and were minimally retargeted (pass `target_col`/`y`); one
tuning test's freq-sev components made well-posed to keep the suite
warning-clean.
Verified: focused five-file run 600 passed; `just check` Ruff/Ty green,
**792 passed, 4 upstream skips** (M31 baseline 764); `git diff --check` clean;
all six reproductions confirmed raising/warning in a pre-test smoke probe
(incl. `group_0` real level preserved as `{'B': 'group_0_1', 'A': 'group_0_1',
'group_0': 'group_0'}` and genuine-`"nan"`-vs-missing split into separate
one-way rows).
Remaining: none. M15 release review is next in a new session.
Blockers: none.
Next action: M15 release review (see its historical handoff below).

## M33 — post-hardening fixes — 2026-09-19

### Scope and completion rules

Follow-up to the committed M31/M32 hardening. A fresh review (plus one
self-review pass) verified residual fail-open paths with runnable probes;
user locked the decisions below. Library-only unless the tutorial exposure
check fails. TDD per chunk: regression fails first, then fix, then focused
pytest; `just check` + `git diff --check` before finishing.

Decisions (2026-09-19):
- `MIN_EXPOSURE = 1.0 / 366.0` (one day in year fractions) with a 0.1%
  relative tolerance for day-count representations: freMTPL2 stores its
  1-day policies a few ulps below `1/366` (min cached exposure
  0.0027322404371584 vs 0.00273224043715847).
- Floor applies to popped exposure columns and portfolio/FSM/table
  validations only; explicit `sample_weight` stays floored-free (severity
  weights are claim counts; sklearn checks feed `arange`-style weights).
- `_pop_weight` raises for a missing configured `exposure_col` only when no
  explicit `sample_weight` is given (M31 over-reach correction).
- `min_exposure` must be `>= MIN_EXPOSURE` and requires a real exposure
  column (raises, mirroring `min_claims`).
- Calibration/one-way tables raise when a segment's summed exposure is below
  the floor; zero weights stay legal for ranking curves (gini/lorenz).
- Deferred to M15 backlog: `set_mapping` unknown-column no-op, distill
  identity-only frame guard, `apply_tariff` overflow, constant-prediction
  qcut NaN group.

| Status | Chunk | Findings addressed |
|---|---|---|
| ☑ | M33-a models weight validation | explicit-weight false positive (F3); GBM negative/NaN weights (F8) |
| ☑ | M33-b one-day exposure floor | min_exposure count fallback (F4); zero-exposure segments (F6); NaN/inf/short-y tariff base (F2) |
| ☑ | M33-c frequency_severity params | params silently ignored + phantom records (F1) |
| ☑ | M33-d small edges | lorenz non-str keys (F5); max_groups; empty profile; empty spec names; metrics labels shrink |

Checkpoint: 2026-09-19 — in progress
Changed: opened M33; verified the tutorial cleaned cache min exposure is a
leap-year 1-day fraction (0.0027322404371584, ~163 ulp below computed
1/366), so the floor uses a 0.1% relative tolerance and keeps all 1,016
1-day rows (none carry claims).
Verified: read-only cache probe; conftest exposure Uniform(0.5, 1.0) is far
above the floor; tutorial YAML floors (1000/2000) are far above it.
Remaining: chunks a–d, checks, docs, push.
Blockers: none.
Next action: chunk M33-a regressions in tests/test_models.py.

Checkpoint: 2026-09-19 — M33-a complete
Changed: `src/azoic/models.py` (`_pop_weight`: finite/non-negative/not-all-zero
weight validation in the shared pop; missing-`exposure_col` raise only when
`sample_weight is None`); `tests/test_models.py` (inverted
`test_freq_sev_subestimator_with_exposure_col_raises` into a coefficient-
equality weighted regression; explicit-override and 4×2 invalid-weight
regressions, all failed before the fix). Commit `db74423`.
Verified: focused `tests/test_models.py` 245 passed incl.
`parametrize_with_checks` with the new weight guards; `tests/test_workflow.py
+ test_tariff.py + test_tune.py` 121 passed.
Remaining: chunks b–d.
Blockers: none.
Next action: chunk M33-b regressions (exposure floor) in test_workflow /
test_metrics / test_preprocessing / test_tariff.

Checkpoint: 2026-09-19 — M33-b complete
Changed: `src/azoic/data.py` (MIN_EXPOSURE/EXPOSURE_FLOOR constants);
`src/azoic/models.py` (popped-column floor, FSM.fit floor);
`src/azoic/workflow.py` (portfolio floor); `src/azoic/metrics.py`
(stability row floor; calibration/one-way segment-sum floors);
`src/azoic/preprocessing.py` (`_check_min_exposure` shared by both classes;
dead ones-fallback removed from `_edges`; docstrings synced);
`src/azoic/tariff.py` (finite totals, y-length, exposure floor in
export/recalibrate). 15 regressions failed before, pass after; 4
`min_exposure=0.0`-without-column tests retargeted to `None`. Commit
`7abab91`. Two test-authoring corrections during the chunk: weighted strata
absorb zero-weight rows (decile scenario replaced by an all-zero portfolio),
and the grouper no-floor sanity fit needs `strategy="rare"` (default
similarity raises target-less per M32).
Verified: focused five-file run 645 passed; cli/tune/data/mlops/plots 116
passed.
Remaining: chunks c–d.
Blockers: none.
Next action: chunk M33-c regressions in tests/test_workflow.py (FSM params).

Checkpoint: 2026-09-19 — M33-c complete
Changed: `src/azoic/workflow.py` (`ModelSpec.build` forwards `params` into
`FrequencySeverityModel`, reserved freq/sev keys raise, special-column
conflicts raise in `effective_params` shared by build and recording);
`tests/test_workflow.py` (5 regressions, all failed before the fix).
Commit `f4bddd3`.
Verified: `tests/test_workflow.py` 72 passed.
Remaining: chunk d.
Blockers: none.
Next action: chunk M33-d regressions (plots/profile/preprocessing/data edges).

Checkpoint: 2026-09-19 — M33-d complete
Changed: `src/azoic/plots.py` (palette lookups stringify like
`model_colors`); `src/azoic/preprocessing.py` (`max_groups >= 1` raise,
dead truthiness guard removed); `src/azoic/profile.py` (empty-profile early
return); `src/azoic/data.py` (`_non_empty` extended to optional specials);
`src/azoic/metrics.py` (level labels via one `np.where`). 6 regressions
failed before, pass after. Commit `bba29ac`.
Verified: plots/preprocessing/profile/data/metrics 366 passed.
Remaining: full `just check`, diff check, final checkpoint, push.
Blockers: none.
Next action: `just check`.

Checkpoint: 2026-09-19 — complete
Changed: `AGENTS.md` (new actuarial rule 12 for the one-day exposure floor);
PRD.md §6 (M33 entry; M31 `_pop_weight` wording corrected to "no explicit
sample_weight"); this milestone's table and checkpoints.
Verified: `uv run ruff check .` green; `uv run ty check` green; full suite
**839 passed, 4 upstream array-api skips** (baseline 792 at the M31/M32 push);
`git diff --check 3f60b0e..HEAD` clean; `ruff format` applied to the four
touched test files (`a5fed20`). Tutorial not re-rendered: the floor is
library-only and the cleaned cache's minimum exposure (one leap-year day,
verified) passes the tolerance; no tutorial YAML floor is below it
(1000/2000).
Remaining: push.
Blockers: none.
Next action: push main.

## Tutorial improvement plan — 2026-09-13

### Scope and completion rules

Keep the existing numbered book, default styling, network-free first-model
guide, library APIs, dependencies, and artifact ignore rules. No new tutorial
framework, model persistence layer, standalone workbook loader, deployment,
automated model selection, or new pricing algorithm is required. Preserve the
existing freMTPL2 cleaning decisions, model parameters, and partitions except
for the explicitly revised tuning experiment. Hide plumbing, but show the
configuration and calculations the reader must understand and change.

| Status | Milestone | Review finding addressed | Dependency |
|---|---|---|---|
| ☑ | M25 — repair executable examples and labels | Broken YAML path; age-band boundary label | None |
| ☑ | M26 — explain the priced population | Missing exclusion evidence and column meanings | M25 |
| ☑ | M27 — teach an adaptable experiment | Hidden configuration; understated prerequisites | M26 |
| ☑ | M28 — work through one policy price | Incomplete scoring and direct-tariff handoff | M27 |
| ☑ | M29 — explain frequency and severity separately | Product-only diagnostics; unrelated tracking | M28 |
| ☑ | M30 — make tuning choices and gains interpretable | Hidden search space; missing comparable baseline | M29 |

For every milestone:

1. Update its status to ◐ and record the starting checkpoint. Complete only its
   scope; incidental findings go in the checkpoint for a later decision.
2. Check off work as it is completed. For changed numerical logic or a defect,
   add the smallest synthetic regression that would catch the error. Reuse
   existing tests; do not add prose snapshots or tests that merely repeat code.
3. Run focused checks, `just check`, `just docs-build`, and `git diff --check`.
   For changed QMD/shared cells, also run
   `OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 just demo` and
   inspect the affected rendered sections, tables, figures, links, and alt text.
4. Execute each affected chapter independently in a fresh temporary directory
   with only its declared cached inputs when its setup/data flow changes. Use
   a bounded sample for this independent check and record the size. Full-book
   rendering and isolated execution are distinct evidence. Automated tests use
   synthetic inputs only; real-data downloads remain manual-render work.
5. Record commands, results, limitations, and generated-artifact locations in
   the checkpoint. Mark ☑ only when required acceptance checks pass, advance
   **Current focus** to the next milestone, and stop. If interrupted or blocked,
   retain ◐ and give the exact remaining action; do not count old checks as new.

Append dated checkpoints under the relevant milestone using this short form:

```text
Checkpoint: YYYY-MM-DD — pending / in progress / complete
Changed: files and completed behaviour
Verified: exact commands, results, and input/sample/cache conditions
Remaining: unchecked work or failed/missing checks
Blockers: concrete condition, or none
Next action: one specific edit or command
```

### M25 — repair executable examples and labels

Make the smallest advertised checkout example runnable and the protected-group
labels faithful to their boundaries.

- [x] Set `examples/tweedie.yaml` to `data_path: synthetic.parquet`. Update the
  matching snippets in the experiment guide and configuration reference,
  explicitly retaining resolution relative to the YAML directory.
- [x] Add a regression that loads the actual shipped YAML (copied beside
  generated synthetic input in a temporary directory) without overriding
  `data_path`, and invokes its fit workflow/CLI from a different working
  directory. Do not substitute a separately constructed test configuration.
- [x] Preserve the protected-group partition and rename the first two labels
  to `30_and_under` and `over_30_to_55`; keep `over_55`. Check ages 29, 30, 31,
  55, and 56 against the chapter's actual construction.
- [x] Run the documented synthetic-data generation and CLI fit from the repo
  root, the common checks above, and render/inspect the protected-group chapter.
  Predictions and group memberships must be unchanged by the label correction.

Initial checkpoint: pending; the review reproduced the resolved path
`examples/examples/synthetic.parquet`. No correction has been applied.
Next action: fix the shipped YAML and its two matching documentation snippets.

Checkpoint: 2026-09-13 — in progress
Changed: started M25; preserved the existing tutorial/library working-tree edits.
Verified: current focus, delivery order, M25 scope, and existing regression patterns.
Remaining: YAML/snippet correction, actual-example and age-boundary regressions,
documented CLI execution, suite/docs checks, and full-book render/inspection.
Blockers: none.
Next action: add regressions for the shipped YAML and chapter age-band construction.

Checkpoint: 2026-09-13 — in progress
Changed: corrected the shipped YAML and both guide/reference paths; renamed
only the chapter's first two age-band labels. Added actual-YAML CLI and actual
chapter-construction regressions (ages 29, 30, 31, 55, 56).
Verified: both regressions failed before the correction and pass afterward;
`just check`: Ruff/Ty green, 684 passed, 4 upstream skips; `just docs-build`:
strict-green; threaded `just demo`: all 11 pages / 115 Python cells passed using
the existing cleaned cache. Generated 20,000 synthetic rows with the documented
command. No model parameters, bins, or library implementation changed.
Remaining: documented CLI result, before/after prediction comparison, rendered
protected-group table inspection, and final diff/ignored-artifact checks.
Blockers: none.
Next action: inspect the rendered table and verify prediction/membership invariance.

Checkpoint: 2026-09-13 — complete
Changed: `examples/tweedie.yaml`, the experiment guide and configuration
reference now use `data_path: synthetic.parquet` and explain YAML-directory
resolution. The protected-group chapter uses `30_and_under`, `over_30_to_55`,
and `over_55` with its existing boundaries. Two synthetic regressions exercise
the unchanged shipped configuration and the chapter's actual age-band assignment.
Verified:
- `uv run pytest tests/test_cli.py::test_cli_fit_shipped_yaml_from_another_directory
  tests/test_tutorial.py::test_protected_age_band_labels_match_chapter_boundaries -q`:
  both failed for the reported defects before correction; both pass afterward.
- From the repository root, ran the documented generation command:
  `uv run python -c "from tests.conftest import make_synthetic_portfolio as m; m(n=20000, seed=42).to_parquet('examples/synthetic.parquet')"`,
  then `uv run azoic fit --config examples/tweedie.yaml`: both configured models
  completed on 20,000 rows (16,000 train / 4,000 test) without path overrides.
- `just check`: Ruff/Ty green, **684 passed, 4 upstream array-API skips**;
  `just docs-build`: strict-green; `uv run ruff format tests/test_cli.py
  tests/test_tutorial.py` and `git diff --check` passed.
- `OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 just demo`:
  **11 pages / 115 Python cells** executed using the existing 667,673-row
  cleaned cache; the protected-group recipe used its default 100,000-row subset.
  No OpenML download was performed; download/clean-cache rebuilding was not tested.
- `uv run python /tmp/azoic-m25-verify.py`: executed shared setup and all protected
  chapter cells in two fresh processes/directories using only a declared 20,000-row
  cleaned-cache sample, with downloads rejected. Before/after label versions have
  exact policy memberships and train/test positions; predictions agree at
  `rtol=1e-12, atol=1e-10`. The comparison requests returned estimators and scores
  only declared features plus exposure. Initial verification-script errors (extra
  input columns and bitwise float comparison) were corrected without source changes.
  Successful logs and arrays: `/tmp/azoic-m25-ancv1lsn/{before,after}/`.
- Headless browser and visual inspection of `examples/_book/09-protected-group.html`
  confirmed readable corrected labels, unchanged default O/P values, and no broken
  images or MathJax errors. All 18 local chapter links resolve. The chapter has no
  figures; no alt text changed. Screenshot: `/tmp/azoic-m25-table.png`.
- `git check-ignore` confirms `examples/synthetic.parquet`, `examples/_book/`,
  `examples/_artifacts/fremtpl2/`, and `site/` outputs remain ignored. Existing
  unrelated source edits were preserved; no commit or publication was performed.
Remaining: none for M25. M26–M30 remain pending.
Blockers: none.
Next action: in the next session, mark M26 in progress and expose the existing
cleaning stages with a sequential audit, preserving every filter and claim cap.

### M26 — explain the priced population

Make data preparation inspectable without changing the population or loss layer.
Primary sources: `examples/01-portfolio.qmd` and `examples/_shared.qmd`.

- [x] Add a compact dictionary for the retained columns: meaning, unit or
  categorical encoding, and role (identifier, outcome, exposure, or predictor).
  Distinguish policy aggregate claim amount from individually capped claims.
- [x] Display a sequential exclusion summary with named rules, removed and
  retained policies, exposure, claim counts, and capped claim amounts. Use
  first-failing-rule attribution so overlapping invalid rows count once.
  Present raw-versus-capped claim totals separately, before exclusions.
- [x] Compute the summary in the existing cleaning path and save an ignored
  `cleaning_audit_v1.csv` beside the cleaned parquet. If the cleaned parquet
  exists but its audit does not, rebuild both from the cached raw OpenML inputs.
  Reuse raw downloads; do not invent audit values from already-cleaned rows.
  Document deletion of both derived caches after cap/cleaning-rule changes.
- [x] Test reconciliation and overlapping exclusions using tiny synthetic raw
  frames. Verify fresh-build and cache-reuse summaries agree and the cleaned
  rows, dtypes, and order match the pre-change loader for identical inputs.
- [x] Run the common checks and isolated portfolio execution with declared raw
  cached inputs. Inspect the audit table and verify the default retained count
  remains 667,673; numerical totals describe the actual configured cap/sample.

Initial checkpoint: pending. Next action: expose the existing cleaning stages
and define their sequential audit without changing any filter or cap.

Checkpoint: 2026-09-13 — in progress
Changed: started M26; existing unrelated working-tree edits are preserved.
Verified: read current focus, M26 scope, the loader and all chapter callers,
and the existing synthetic reporting smoke test.
Remaining: dictionary, sequential audit/cache handling, synthetic regressions,
full checks/render, isolated raw-cache execution, and rendered-table inspection.
Blockers: none.
Next action: record each existing cleaning rule's first-failure totals in the loader.

Checkpoint: 2026-09-13 — in progress
Changed: added the retained-column dictionary and live cap/exclusion/sample tables;
loader saves `cleaning_audit_v1.csv` and rebuilds both derived caches if either is
missing. Existing masks, join, cap, column selection, and sampling are preserved.
The reporting smoke now creates both caches through the real loader from synthetic
raw frames. No new dependency, library API, model parameter, or partition changed.
Verified: synthetic audit test passes for 13 raw policies, overlapping failures,
per-claim cap, unmatched severity, signed/missing totals, reconciliation, sampling,
cache reuse, and each missing-cache rebuild. Reporting and age-label smokes passed.
Initial test-only dtype assumptions and arithmetic totals were corrected.
Remaining: baseline loader comparison, full suite/docs/book checks, isolated
portfolio raw-cache execution, rendered tables/links, and artifact ignore checks.
Blockers: none.
Next action: compare the old/new loaders on identical raw inputs and run acceptance.

Checkpoint: 2026-09-13 — in progress
Changed: documented the paired-cache convention in `AGENTS.md` and `PRD.md`;
hid audit-table formatting code after inspecting the rendered reading flow.
Verified: `just check`: Ruff/Ty green, 685 passed, 4 upstream skips;
`just docs-build`: strict-green; threaded `just demo`: all 11 pages executed.
`uv run python /tmp/azoic-m26-verify.py`: two fresh processes with copied raw
OpenML caches and downloads rejected; old/new cleaned frames and 20,000-policy
samples match exactly, including dtypes and order. Full retained count: 667,673.
The current portfolio chapter's 11 cells execute independently, with matching
fresh-build/reuse audits. Evidence: `/tmp/azoic-m26-uiy0_emv/{before,after}/`.
Remaining: rerender after hiding formatting code; final visual/table/link checks
and completion handoff. Generated audit, parquet, book, and site remain ignored.
Blockers: none.
Next action: inspect the final rendered portfolio tables and record acceptance.

Checkpoint: 2026-09-14 — complete
Changed: `examples/01-portfolio.qmd` explains all 13 retained columns and shows
separate live claim-cap, sequential exclusion, and modelling-sample totals.
`examples/_shared.qmd` saves `cleaning_audit_v1.csv` alongside the cleaned parquet;
either missing cache triggers rebuilding both from raw inputs. First-failing-rule
attribution preserves all existing filters and per-claim capping. Paired-cache
invalidation is documented in the chapter, `AGENTS.md`, and `PRD.md`.
Verified:
- `uv run pytest tests/test_tutorial.py::test_portfolio_audit_reconciles_first_failures_and_cache_rebuilds -q`:
  passed. Thirteen synthetic raw policies exercise overlapping failures, missing
  and signed values, per-claim capping, unmatched severity IDs, reconciliation,
  row order/dtypes, sampling, cache reuse, and rebuilding either missing cache.
  The existing fresh-process reporting smoke creates both caches through the
  real loader from synthetic raw frames and rejects downloads during execution.
- `just check`: Ruff/Ty green, **685 passed, 4 upstream array-API skips**.
  `uv run ruff format tests/test_tutorial.py` passed. `just docs-build` passed
  strict mode, including a repeat after the final convention/documentation edits.
- `OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 just demo`:
  final render passed **11 pages / 117 Python cells**. The first render rebuilt
  the previously unaudited cleaned cache from the existing raw OpenML cache;
  the final render reused the paired caches. Main chapters use all 667,673
  cleaned policies; tuning/protected-group recipes retain their 100,000-row cap.
- `uv run python /tmp/azoic-m26-verify.py`: old and new loader executions in
  separate fresh processes/directories, each with only copied raw OpenML cached
  inputs and downloads rejected. Exact DataFrame equality verifies all **667,673
  cleaned rows**, dtypes, column/row order, and the **20,000-policy** sample.
  The new portfolio chapter's 11 cells execute independently; repeated loading
  reproduces the same sample and audit. Logs and artifacts are under
  `/tmp/azoic-m26-uiy0_emv/{before,after}/`. Fresh network downloads were not tested.
- The full audit starts with **678,013** joined policies, removes **1,224** for
  exposure and then **9,116** for inconsistent count/amount; other rules remove
  zero on these pinned inputs. Retained totals are **352,530.648031 policy-years**,
  **26,391 claims**, and **EUR 49,214,268.67**. Raw severity totals before joining
  are **EUR 60,697,930.68**, capped to **EUR 49,964,409.11** at **EUR 100,000 per
  claim**. Every sequential policy/exposure/count/amount total reconciles.
- `uv run python /tmp/azoic-m26-final-checks.py`: **71 local links/anchors**
  resolve, and the rendered audit/cleaned cache exactly equal the independently
  rebuilt versions. Final headless inspection and screenshots confirm readable
  dictionary, cap, and both exclusion tables; all eight chapter tables fit the
  749-pixel content column. Zero MathJax errors or broken images; this chapter
  contains no figures, so no figure alt text changed. Screenshots:
  `/tmp/azoic-m26-{dictionary,cap,audit-final}.png`. Early browser attempts during
  the rerender were repeated successfully after Quarto recreated the output.
- `git diff --check` and artifact ignore checks passed. The audit CSV, parquet
  caches, generated book, and docs site remain ignored. Existing unrelated edits
  were preserved; no commit, dependency change, or publication was performed.
Remaining: none for M26. M27–M30 remain pending.
Blockers: none.
Next action: in the next session, mark M27 in progress and introduce the model
roles and visible experiment configuration without changing the fitted candidates.

### M27 — teach an adaptable experiment

Readers should understand and modify the experiment before invoking a helper.
Primary sources: `examples/index.qmd`, `examples/02-experiments.qmd`, and the
existing first-model/experiment guides.

- [x] Define GLM (generalized linear model), GBM (gradient-boosted trees), the
  log link, and why direct Tweedie fits a zero-heavy non-negative claim-cost
  target. Explain each model's practical role before its settings. Link the
  existing network-free first-model guide from the book's entry page.
- [x] Assemble the current configurations in short visible, executable cells:
  dataset contract and features, preprocessing, named models, then experiment.
  Introduce the direct GLM baseline before the raw-feature GBM benchmark.
  Keep the structured teacher's explanation/specification collapsible and
  optional; preserve all three candidates, two run identities, and parameters.
- [x] Keep `_shared.qmd` as the canonical reusable configuration for other
  chapters; check that the chapter's explicit configuration equals its helper
  output. Hide plotting/download setup and move detailed merge mechanics to
  the fitted-structure inspection. Do not change the calibration/split safeguards.
- [x] Add a compact "Use your own portfolio" example with explicit imports,
  Parquet input, named outcome/exposure columns, feature list, and one GLM.
  Show `return_estimators=True`, `predict`, and rate-to-cost conversion. Explain
  that YAML paths are config-relative, Python paths use the working directory,
  and identifiers/outcomes/protected attributes are excluded from features.
  Use random splitting when no real time field exists; link the temporal recipe.
- [x] Execute that exact adaptation snippet on synthetic data, check visible
  config/helper parity, and confirm existing run identities and train/test
  positions. Run common checks and isolated experiment execution; inspect the
  reading order and links without relying on the shared source being visible.

Initial checkpoint: pending. Next action: introduce the model roles and expose
the existing configuration in the experiment chapter, without altering fits.

Checkpoint: 2026-09-14 — in progress
Changed: started M27; preserving all pre-existing working-tree edits.
Verified: read current focus, M27 scope, shared configurations and chapter flow.
Remaining: visible configuration, adaptation example, synthetic execution/parity,
common acceptance checks, isolated chapter execution, and rendered inspection.
Blockers: none.
Next action: expose the existing configurations in teaching order.

Checkpoint: 2026-09-14 — in progress
Changed: entry page links the network-free first model and explains Quarto setup;
experiment chapter defines model roles, exposes dataset/preprocessing/models/run
configuration, defers merge details and the optional teacher, and adds a standalone
Parquet-to-rate-to-cost example. Shared configuration and model parameters unchanged.
Verified: strict `just docs-build` passed. Initial synthetic checks caught tuple
indexing in the new snippet and an incorrect test assumption about the random split;
both corrected. Tests now compare partitions to the canonical helper's actual run.
Remaining: corrected focused/full checks, full render, isolated 20,000-row chapter
execution, final reading-order/link/visual checks and artifact verification.
Blockers: none.
Next action: collect acceptance results and inspect the rendered experiment chapter.

Checkpoint: 2026-09-14 — complete
Changed: `examples/index.qmd` links the network-free first-model guide and explains
Quarto prerequisites. `examples/02-experiments.qmd` defines GLM, GBM, log link,
and Tweedie suitability before showing executable data, preprocessing, candidate,
and experiment configuration. Teacher details are collapsed; merge mechanics
follow fitting. The standalone own-portfolio snippet imports its dependencies,
loads named Parquet columns, fits one GLM, scores without outcomes, and converts
raw rates to period costs. It explains feature exclusions, path resolution,
random/temporal splitting, and the simple numeric-age model's boundary.
Verified:
- `uv run pytest tests/test_tutorial.py -q`: **5 passed**. Existing fresh-process
  assembly smoke now also executes the experiment chapter using 4,000 synthetic
  policies, only paired input caches, and rejected downloads. Visible configs equal
  the unchanged helper output, both run names and all three candidates persist,
  and train/test positions exactly match a separate canonical-helper run.
  The exact standalone snippet runs on 1,000 synthetic policies (200 held out),
  predicts finite positive rates, and computes rate times exposure. Doubling
  scoring exposure leaves predicted rates unchanged.
- Final `just check`: Ruff/Ty green, **687 passed, 4 upstream array-API skips**.
  The first full-suite process had collected the old split-test assumption and
  failed that test; the fresh corrected suite passed. `uv run ruff format
  tests/test_tutorial.py`, `just docs-build` (strict), and `git diff --check` passed.
- `OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 just demo`:
  **11 pages / 122 Python cells** passed using existing paired caches. Main
  chapters used 667,673 cleaned policies; capped recipes retained their defaults.
  After correcting the snippet during that render, separately refreshed
  `examples/index.qmd` and `examples/02-experiments.qmd` with the same thread limits
  and `uv run quarto render`; the final experiment refresh passed all 15 cells.
- `uv run python /tmp/azoic-m27-verify.py`: all experiment cells ran in a fresh
  process/directory with only a declared 20,000-policy cleaned-cache sample and
  companion audit, with downloads rejected. No prior estimator/report/workbook
  was supplied. Config parity and exact canonical-run positions passed (16,000
  train / 4,000 test). Evidence: `/tmp/azoic-m27-p28e0pgl/execution.log`.
  Network downloading and raw-cache rebuilding were not part of this milestone.
- `uv run python /tmp/azoic-m27-links.py`: **205** local links/anchors and
  published-guide targets in the local strict site build resolve. Context7's
  current Quarto documentation confirmed the separate CLI/Python prerequisites.
  Headless browser and screenshot inspection verified reading order, visible
  settings, collapsed teacher, training-structure tables, entry link, and corrected
  adaptation snippet. No broken images or MathJax errors; these pages add no figures.
  Screenshots: `/tmp/azoic-m27-{entry,configuration,adaptation}.png`.
- `git check-ignore examples/_book/ examples/_artifacts/fremtpl2/ site/` confirms
  generated outputs remain ignored. Shared configuration, library APIs, model
  settings, dependencies, and pre-existing unrelated edits were preserved.
Remaining: none for M27. M28–M30 remain pending.
Blockers: none.
Next action: in the next session, mark M28 in progress and add the outcome-free
worked policy immediately after direct GLM export in `04-scoring-tariff.qmd`.

### M28 — work through one policy price

Complete the main path with an inspectable direct GLM calculation before the
optional distillation extension. Primary source: `examples/04-scoring-tariff.qmd`.

- [x] Select the held-out policy with the lowest policy ID, without consulting
  its outcomes or predicted cost. Display its ID, raw rating inputs, exposure,
  and fitted bin/group assignments; retain IDs in the scored output.
- [x] Read the direct workbook's base/factors and show each selected factor
  and their multiplication into this policy's raw rate. Reuse fitted
  preprocessing and the existing workbook-factor application recipe; explain
  that this is not standalone reconstruction from Excel mappings.
- [x] Show raw rate, frozen training O/P multiplier, adjusted rate, and both
  expected period costs (`rate * exposure`) in one compact result. Explain
  the workbook remains raw and adjustment is external. Add the corresponding
  expected-cost columns to the scored DataFrame, with explicit scale labels.
- [x] Verify workbook/manual-factor application equals raw GLM prediction
  (`rtol=1e-6`, `atol=1e-8`), adjusted output equals the scoring result, and
  cost equals rate times exposure. The worked scoring path must use no claim
  columns. Reuse synthetic tariff checks and execute the actual chapter cells.
- [x] Run common checks and isolated scoring/tariff execution with no existing
  workbook or estimator. Inspect the worked policy before the stated stopping
  point; retain the existing distillation and held-out claims comparisons.

Initial checkpoint: pending. Next action: add the outcome-free worked policy
immediately after the direct GLM export, using that chapter's fitted objects.

Checkpoint: 2026-09-14 — in progress
Changed: started M28; preserving all pre-existing working-tree edits.
Verified: read current focus, M28 scope, scoring/export flow, workbook application,
and the synthetic chapter assembly checks.
Remaining: worked policy, labelled rates/costs and IDs, synthetic checks, full
checks/render, isolated scoring execution, and rendered inspection.
Blockers: none.
Next action: extend scoring output and apply direct-workbook factors to the
lowest-ID held-out policy using only rating inputs and exposure.

Checkpoint: 2026-09-14 — in progress
Changed: scoring retains policy IDs/exposure and explicit raw/adjusted rate and
period-cost columns. The lowest-ID held-out policy shows raw inputs, fitted
levels, selected workbook factors, base/product, frozen training O/P, and costs.
Both workbook examples reuse the existing factor-reading recipe in a local
chapter function; the direct workbook remains raw. No library/config changes.
Verified: the new synthetic chapter regression first failed because the worked
policy was absent. It executes the full chapter and replays scoring after removing
outcomes and doubling exposure. Acceptance execution is in progress.
Remaining: focused/full checks, docs/book build, isolated 20,000-policy execution,
rendered table/figure/link inspection, and final artifact/diff checks.
Blockers: none.
Next action: collect the synthetic regression and run common acceptance checks.

Checkpoint: 2026-09-14 — in progress
Changed: completed the worked-price cells and reused workbook reading in the
optional extension; moved numerical verification out of the visible calculation.
Verified: focused synthetic scoring test passed (4,000 policies); strict
`just docs-build` passed; `git diff --check` and generated-output ignore checks
passed. `uv run python /tmp/azoic-m28-verify.py` passed in a fresh process/directory
with only a 20,000-policy cleaned-cache sample and companion audit; downloads
were rejected and both workbooks/models were built afresh. All chapter cells,
eight optional comparison rows, and canonical partition equality passed (16,000
train / 4,000 test). Evidence: `/tmp/azoic-m28-mkh_ns1g/execution.log`.
Remaining: running `just check` and threaded `just demo`, rendered inspection,
and final completion checkpoint.
Blockers: none.
Next action: inspect the fresh scoring chapter once the full-book render reaches it.

Checkpoint: 2026-09-14 — in progress
Changed: no further implementation changes.
Verified: `just check` passed Ruff/Ty and **688 tests, 4 upstream array-API skips**.
The full scoring render has passed the worked policy's workbook/model/scoring
assertions and is finishing its retained optional figures.
Remaining: complete full-book rendering and visual/link/table inspection.
Blockers: none.
Next action: inspect the rendered worked-policy tables and retain M28 in progress
until the complete book render passes.

Checkpoint: 2026-09-14 — in progress
Changed: visual review found the worked-price equation exceeded the reading
column; split it into two aligned lines and wrapped two visible Python lines.
Verified: staged scoring HTML has readable nine-factor and compact price tables,
all five images load, and MathJax reports no errors. Full-data policy 811 has
exposure 0.76, raw rate 121.965359, adjusted rate 121.742112, and expected costs
92.693673 / 92.524005. Tables fit the default theme's 749-pixel reading column.
Remaining: finish full render, refresh scoring HTML after the equation-only
presentation fix, inspect final equation/links/figures, and complete the checkpoint.
Blockers: none. Early inspection attempted `_book` before Quarto assembled it;
staged `examples/04-scoring-tariff.html` was available and inspected instead.
Next action: after `just demo`, render `examples/04-scoring-tariff.qmd` once more
with the same thread limits, then inspect the final page.

Checkpoint: 2026-09-14 — complete
Changed: `examples/04-scoring-tariff.qmd` retains policy IDs/exposure and explicit
raw/adjusted rate and expected-period-cost columns for every candidate. The
lowest-ID held-out policy shows its outcome-free inputs, nine fitted levels and
workbook factors, base/product, raw rate, frozen training O/P, adjusted rate, and
both costs before the main-path stopping point. A local chapter function reuses
the existing workbook-factor recipe for both exports; fitted preprocessing is
still required and the direct workbook remains raw. The optional distillation
and held-out claims comparisons remain intact. `tests/test_tutorial.py` extends
the existing fresh-process synthetic assembly test; no library/API/dependency,
shared configuration, cleaning, model parameter, or partition changes were made.
Verified:
- `uv run pytest 'tests/test_tutorial.py::test_chapter_builds_its_own_artifacts_in_fresh_process[04-scoring-tariff.qmd]' -q`:
  failed first on the missing worked policy, then passed, including a final repeat
  after the equation/line-wrapping edit. The full chapter runs on 4,000 synthetic
  policies with only paired input caches and rejected downloads. Replaying actual
  scoring cells after removing claim columns and shuffling held-out rows preserves
  IDs/prices; doubling exposure preserves rates and doubles period costs. Manual
  factors, workbook application, GLM prediction, and scoring agree at the required
  tolerance; the eight optional claims-comparison rows still execute.
- `just check`: Ruff/Ty green, **688 passed, 4 upstream array-API skips**.
  `uv run ruff format tests/test_tutorial.py`, strict `just docs-build`, and
  `git diff --check` passed. Subsequent edits only wrapped the displayed equation
  and two Python expressions; the focused test and chapter execution passed again.
- `OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 just demo`:
  **11 pages / 127 Python cells** passed with existing paired caches. After the
  visual layout correction, `OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2
  uv run quarto render examples/04-scoring-tariff.qmd` passed all **21 cells**.
  No OpenML download or raw-cache rebuilding was tested in this milestone.
- `uv run python /tmp/azoic-m28-verify.py`: all scoring chapter cells passed in a
  fresh process/directory with only a declared **20,000-policy** cleaned-cache
  sample and companion audit, downloads rejected, and no workbook or estimator
  supplied. Both exports were rebuilt, all eight claims-comparison rows executed,
  and exact canonical-run positions agreed (**16,000 train / 4,000 test**).
  Evidence: `/tmp/azoic-m28-mkh_ns1g/execution.log` and its artifact directory.
- Final `uv run python /tmp/azoic-m28-links.py`: **317 links/anchors** resolve.
  Headless inspection with `/tmp/azoic-m28-inspect.py` and screenshots verified the
  factor/result tables, raw/adjusted units, external multiplier, and stopping point
  before the optional extension. The corrected equation is 472 pixels wide in
  the 749-pixel reading column; no MathJax errors. All five retained figures load
  with descriptive alt text and were visually inspected. Screenshots:
  `/tmp/azoic-m28-factors-final.png`, `/tmp/azoic-m28-price-final.png`, and
  `/tmp/azoic-m28-plots-review.png`.
- Full-data worked policy **811** has exposure **0.76**, base **48.053870**, factor
  product **2.538096**, raw/adjusted rates **121.965359 / 121.742112**, and expected
  costs **92.693673 / 92.524005**. These are rendered evidence, not solver goldens.
- `git check-ignore examples/_book/ examples/_artifacts/fremtpl2/ site/` confirms
  generated artifacts stay ignored. All pre-existing unrelated edits were preserved;
  no commit or publication was performed.
Remaining: none for M28. M29–M30 remain pending.
Blockers: none.
Next action: in the next session, mark M29 in progress and obtain component
predictions from the existing frequency/severity models for weighted diagnostics.

### M29 — explain frequency and severity separately

Make the decomposition useful for diagnosis and remove operations unrelated to
the lesson. Primary source: `examples/06-frequency-severity.qmd`.

- [x] Explain when separate incidence and claim-size models help interpretation
  and why the product still needs its own calibration assessment. Use public
  fitted `freq_` and `sev_` attributes, with the existing fitted preprocessing
  for the GLM; do not add prediction wrappers or a new library interface.
- [x] Show raw predicted frequency, severity, and their product for a small
  policy sample. Verify the product reproduces the composite raw prediction.
  A training O/P adjustment applies to the product, not to both components.
- [x] Add held-out component calibration tables for each GLM/GBM alternative:
  frequency compares claim counts with rates using exposure weights on all
  rows; severity compares claim amounts with cost-per-claim predictions using
  claim-count weights on positive-claim rows only. Show supporting exposure or
  claim counts and interpret a concrete discrepancy from the rendered results.
- [x] Explain the actual product comparison with direct Tweedie on the same
  holdout, without claiming superiority from one split. Remove this chapter's
  automatic MLflow setup/logging and report/dashboard writes; link reporting
  for those optional operations. Retain the in-page model comparison.
- [x] Test component weights, positive-claim filtering for severity diagnostics,
  product equality, and outcome-free prediction using synthetic chapter cells.
  Run common checks and isolated chapter execution without an MLflow store or
  earlier reports. Training populations and existing product fits stay unchanged.

Initial checkpoint: pending. Next action: obtain component predictions from
the existing fitted models before their product-level adjustment.

Checkpoint: 2026-09-14 — in progress
Changed: started M29; preserved all existing working-tree changes.
Verified: component attributes, fitted preprocessing, calibration-table units,
and existing synthetic chapter assembly checks.
Remaining: component examples/tables, interpretation, operations removal,
synthetic regression, isolated execution, full render and common checks.
Blockers: none.
Next action: expose raw component predictions and correctly weighted diagnostics.

Checkpoint: 2026-09-14 — in progress
Changed: chapter uses fitted component attributes and GLM preprocessing, shows
raw policy examples and four weighted calibration tables, and retains raw/adjusted
product comparisons. Removed chapter MLflow setup/logging and report/dashboard
writes; linked the existing operations recipe. Added a synthetic chapter regression.
Verified: `uv run pytest tests/test_tutorial.py -k 06-frequency -q`: 1 passed;
checks exact diagnostic arrays/weights, positive-claim filtering, product equality,
outcome-free prediction, and absence of operations artifacts with MLflow blocked.
`just docs-build`: strict-green. Ruff formatting passed.
Remaining: concrete full-data interpretation, full suite/book render, isolated
20,000-row execution, rendered inspection and final diff checks (running).
Blockers: none.
Next action: inspect rendered component and product results and explain discrepancies.

Checkpoint: 2026-09-14 — in progress
Changed: implementation and synthetic regression complete; full-data interpretation
and rendered inspection remain.
Verified: `just check`: Ruff/Ty green, **689 passed, 4 upstream array-API skips**.
`uv run python /tmp/azoic-m29-verify.py`: fresh process/directory, 20,000 cached
policies, 16,000 train / 4,000 test, paired cleaned cache/audit only; downloads
and MLflow imports rejected. Component/product assertions passed, with only
three parquet/audit cache files present afterward. Evidence is under
`/tmp/azoic-m29-tz644r57/`. The bounded sample emitted the existing warning for
categorical levels with no positive training claims; no fit settings were changed.
`git diff --check` and generated-artifact ignore checks passed.
Remaining: full book render (now in optional recipes), concrete interpretation,
visual and link review, final checkpoint.
Blockers: none.
Next action: read the full-data component tables after chapter 06 renders.

Checkpoint: 2026-09-14 — in progress
Changed: added concrete interpretation of full-data GLM/GBM component discrepancies
and product tradeoffs against direct Tweedie, with the default population stated.
Verified: threaded `just demo` passed **11 pages / 131 Python cells** on existing
667,673-row paired caches. Chapter 06 passed its 12 cells and stored-partition,
component-product, raw-run metric, training-factor, and Gini-invariance assertions.
Raw product deviances remain **75.237864 / 74.560943** for GLM/GBM, matching the
previous implementation. Browser inspection checked all nine tables: no page
overflow, broken images, or MathJax errors; this chapter has no figures.
Remaining: chapter refresh for the added prose, final rendered link/visual check,
and completion checkpoint. No numerical cells changed after the green suite/render.
Blockers: none.
Next action: inspect the final refreshed chapter and mark M29 complete.

Checkpoint: 2026-09-14 — complete
Changed: `examples/06-frequency-severity.qmd` now explains the component units,
uses public `freq_`/`sev_` with existing fitted preprocessing, shows five common
held-out policies and four correctly weighted component tables, and interprets
observed discrepancies and direct-Tweedie product tradeoffs. The training factor
applies once to the product. Removed automatic MLflow/report/dashboard writes and
linked the operations recipe. `tests/test_tutorial.py` exercises the actual chapter
cells with synthetic data, including exact weights/filtering, product equality,
outcome-free predictions, and cache-only artifacts while MLflow is unavailable.
Verified:
- `uv run pytest tests/test_tutorial.py -k 06-frequency -q`: **1 passed**.
- `just check`: Ruff/Ty green, **689 passed, 4 upstream array-API skips**;
  `just docs-build`: strict-green. Later chapter edits added explanatory prose only.
- `OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 just demo`:
  **11 pages / 131 Python cells** passed using existing paired caches, including
  all full-portfolio component/product assertions. No OpenML download or cache
  rebuilding was needed; those paths were not retested in M29.
- After adding the interpretation, `OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
  MKL_NUM_THREADS=2 uv run quarto render examples/06-frequency-severity.qmd`
  passed all **12 cells** on **667,673 policies**, with **534,138 training /
  133,535 test** rows. Product fits/metrics are unchanged.
- `uv run python /tmp/azoic-m29-verify.py`: isolated **20,000-row** execution
  passed with only the declared paired caches, no downloads, no MLflow store,
  and no earlier reports; evidence in `/tmp/azoic-m29-tz644r57/execution.log`.
- `uv run python /tmp/azoic-m29-inspect.py examples/_book/06-frequency-severity.html`:
  all nine tables inspected, units/support and scale labels visible, no page
  overflow or MathJax errors; no figures were added. Screenshots are under
  `/tmp/azoic-m29-table-*.png`. The reused local-link checker resolved **151**
  links/anchors, including the operations recipe. Whitespace and ignore checks
  passed; generated book/cache outputs remain ignored.
Remaining: none for M29. M30 remains pending; no library APIs, dependencies,
model settings, training populations, or partitions changed.
Blockers: none.
Next action: in the next session, mark M30 in progress and expose its bounded
tuning spaces and comparable untuned baseline. Stop here.

### M30 — make tuning choices and gains interpretable

Teach a bounded, predeclared experiment rather than an unexplained search.
Primary source: `examples/07-tuning.qmd`; reuse the operations/configuration
guides for the existing typed search-space contract.

- [x] Keep the seeded subset of at most 100,000 rows and eight Python trials
  per model. Declare explicit custom spaces: GLM `alpha` logarithmically from
  `1e-4` to `0.1`; structured GBM `num_leaves` from 8 to 32 in steps of 8.
  Other base parameters remain fixed. Explain that each custom model space
  replaces that model's built-in space and why these bounds are illustrative.
- [x] Keep `calibration_penalty=1.0` and show that O/P 1.10 contributes 0.10
  to the objective. Compare the penalty contribution with deviance; select
  any future penalty or search bounds inside training data, never from the
  displayed outer-test result.
- [x] Define the untuned baseline config before either evaluation, using the
  same subset, features, preprocessing, seed, and outer partition. Fit it once
  and compare baseline/tuned raw outer-test deviance, O/P, and Gini side by
  side. Assert equal fingerprints and exact train/test positions. A gain is
  measured, not required; do not compare these numbers with the full portfolio.
- [x] Retain the selected-estimator scoring/export handoff and four-trial CLI
  example as a separately labelled search. Show readable YAML for the explicit
  spaces and point to existing CLI precedence documentation.
- [x] Extend synthetic chapter coverage for declared ranges, baseline/selected
  partition equality, fixed parameters, and the existing untouched-holdout
  guarantee. Run common checks and isolated tuning execution, including its
  own YAML, CLI report, and workbook outputs.
- [x] At the final handoff, confirm all six milestones are green, inspect the
  complete book's main path and optional links, and record fresh whole-book,
  strict-docs, and suite evidence. List any real-download or deployment checks
  not performed. Set the next task to the separate M15 release review and stop.

Initial checkpoint: pending. Next action: declare both search spaces and the
untuned baseline before running any study or displaying outer-test results.

Checkpoint: 2026-09-14 — in progress
Changed: started M30; preserving all pre-existing working-tree edits.
Verified: current focus, M30 scope, shared configuration, tuning implementation,
and the existing synthetic chapter assembly checks.
Remaining: explicit spaces/baseline, penalty explanation, comparison and YAML,
synthetic/isolated checks, full suite/docs/book render and final book inspection.
Blockers: none.
Next action: extend the synthetic chapter regression, then declare both bounded
spaces and the baseline before evaluation.

Checkpoint: 2026-09-14 — in progress
Changed: explicit GLM alpha and GBM leaf-count spaces, predeclared untuned
baseline, worked penalty, raw side-by-side holdout metrics/gains, generated YAML,
and links to the existing search contract/CLI precedence. The synthetic assembly
test now executes tuning, its real CLI command, and an altered-outer-claims rerun.
Verified: focused tuning chapter test passed on 4,000 synthetic policies, including
fixed parameters, exact partitions/fingerprints, metric reproduction, YAML reload,
report/workbook outputs, and unchanged selections after holdout claims changed.
The first CLI smoke exposed missing project metadata in the temporary test harness;
a minimal project table plus the existing offline environment fixes that setup.
Strict docs passed. Full check stopped on one 102-character test line, now wrapped.
Remaining: rerun full check, complete book render, isolated tuning and final
whole-book visual/link checks. Generated outputs remain ignored.
Blockers: none.
Next action: run isolated 20,000-policy tuning including its own CLI/YAML/workbook.

Checkpoint: 2026-09-14 — in progress
Changed: no further implementation changes after the lint-only line wrap.
Verified: `just check` passed Ruff/Ty and 690 tests, 4 upstream array-API skips;
`just docs-build` passed strict mode. `uv run python /tmp/azoic-m30-verify.py`
passed all tuning cells in a fresh directory with only 20,000 cached policies
and the companion audit, downloads rejected. Baseline/selected positions and
fingerprints match (16,000 train / 4,000 test); its own Python report, raw workbook,
YAML reload, and real four-trial CLI report passed. Evidence is under
`/tmp/azoic-m30-fapky_cs/`. Whitespace and generated-output ignore checks passed.
Remaining: full render is executing chapter 07; inspect its results and the
complete book's main-path/optional links before the final M15 handoff.
Blockers: none.
Next action: inspect the fresh tuning HTML, then run whole-book browser/link checks.

Checkpoint: 2026-09-14 — complete
Changed: `examples/07-tuning.qmd` declares logarithmic GLM alpha [1e-4, 0.1]
and structured-GBM leaves {8, 16, 24, 32}, eight Python trials per model, and an
untuned baseline before fitting. It explains custom-space replacement, fixed
settings, the 0.10 penalty contribution at O/P 1.10, and training-only choices.
Raw baseline/tuned deviance, O/P, and Gini appear side by side with measured gains.
Selected-estimator scoring/raw export remain executable; readable generated YAML
and the separately labelled four-trial CLI search link to existing precedence docs.
`tests/test_tutorial.py` extends the existing fresh-process assembly check, with
minimal project metadata and the installed offline environment for its real CLI.
Verified:
- `uv run pytest tests/test_tutorial.py -k 07-tuning -q`: **1 passed**, including
  a final repeat after display-only line wrapping. On 4,000 synthetic policies it
  checks declared bounds, only the intended sampled parameters, fixed settings,
  exact baseline/selected fingerprints and partitions, raw metric reproduction,
  YAML reload, CLI report, and workbook. Multiplying only outer-test claims by ten
  leaves selected parameters and inner objectives unchanged while outer deviance
  changes. The existing random/temporal untouched-holdout regressions also pass.
- `just check`: Ruff/Ty green, **690 passed, 4 upstream array-API skips**.
  `just docs-build`: strict-green. The only subsequent executable-source changes
  split two displayed Python lines without changing expressions; the focused
  regression and full tuning chapter passed again. Ruff format and final
  `git diff --check` passed.
- `OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 just demo`:
  **11 pages / 136 Python cells** passed with existing paired caches for the
  **667,673-policy** cleaned portfolio. Tuning uses its seeded **100,000-policy**
  subset and identical **80,000 train / 20,000 test** partitions. After visual
  line wrapping, the same thread limits with `uv run quarto render
  examples/07-tuning.qmd` passed all **16 cells**, including the separate CLI.
  Logs: `/tmp/azoic-m30-{demo,chapter,check,docs}.log`.
- `uv run python /tmp/azoic-m30-verify.py`: isolated **20,000-policy** execution
  passed in a fresh process/directory with only the cleaned-cache sample and its
  companion audit, downloads rejected, and no supplied models, YAML, reports, or
  workbook. Baseline/selected partitions agree (**16,000 / 4,000**); the chapter
  created its own Python report, raw workbook, YAML, and real CLI report.
  Evidence: `/tmp/azoic-m30-fapky_cs/execution.log` and its artifact directory.
- `uv run python /tmp/azoic-m30-book-inspect.py examples/_book` inspected all
  **11 pages**: all **12 figures** load with alt text, with no MathJax errors or
  page overflow. Main-path entry, column meanings, adaptable experiment,
  diagnostics, worked price, stopping points, and optional navigation were
  reviewed. Tuning tables, fixed ranges, penalty, and YAML were visually checked;
  its two clipped code lines were wrapped and the refreshed comparison rechecked.
  Browser reports/screenshots are `/tmp/azoic-m30-*inspection*` and
  `/tmp/azoic-m30-*.png`. The final `/tmp/azoic-m30-links.py` resolves **1,710**
  local links/anchors and corresponding published-guide targets in the local site.
- On the declared subset, raw GLM deviance changes **68.209744 → 67.972580**,
  O/P **0.875615 → 0.889797**, Gini **0.253194 → 0.258404**. Structured GBM
  changes **68.582483 → 67.092046**, **1.126262 → 0.985628**, and
  **0.271255 → 0.305912** respectively. Selected alpha is about **0.071145**;
  selected leaves are **8**. These are one-split rendered observations, not
  required improvements or exact solver goldens; no full-portfolio gain is claimed.
- Context7's current Optuna documentation confirmed logarithmic and stepped
  distributions. No public APIs, dependencies, shared model settings, cleaning,
  or main-path partitions changed. Generated book/site/cache/report/workbook
  artifacts remain ignored; all pre-existing unrelated edits were preserved.
Limitations: no fresh OpenML download or raw-cache rebuild was performed. No
new distribution build, release publication, deployment, or live-site check was
performed; M15 must repeat its release checks on the corrected source.
Remaining: none for M30. **M25–M30 are all complete.**
Blockers: none.
Next action: in a separate session, perform the M15 release review and repeat
its distribution builds and isolated CLI checks before publication. Stop here.

## Milestones

- ☑ **Tutorial editorial and execution revision** — completed 2026-09-11
  within M24's scope; no new implementation milestone.
  - [x] Reporting creates and logs only its own reports; both CLI workbooks use
    `--no-recalibrate` to preserve the evaluation boundary.
  - [x] Replaced unsupported pass claims with actual-result interpretation and
    open review questions; restored capped-loss impact and operational limits.
  - [x] Main path ends at scoring and direct GLM tariff review. Deeper diagnostics,
    distillation, and later recipes are optional. Shared setup is hidden, tables
    fit the reading column, all 12 plots have alt text, and inline math renders.
  - [x] Documented manual cleaned-cache invalidation and bounded recipe samples
    by available rows; tuned estimators now feed executable scoring/export.
  - [x] Added a fresh-process synthetic reporting assembly test (real setup,
    fits, reports, and MLflow). It exposed a final-two-bin merge error:
    `_merge_small_bins` now pops the last weight before adding it to the remaining
    neighbour. A minimal two-bin regression covers the shared exposure/claim floor.
  - [x] `just check`: Ruff/Ty green, **682 passed, 4 upstream skips**;
    `just docs-build`: strict-green; final `just demo`: **11 pages / 115 Python
    cells**, with OMP/OpenBLAS/MKL threads limited to two. The existing numerical
    tutorial regression also passed after display changes.
  - [x] Independently executed reporting (including CLI), tuning (including
    export), and protected-group reporting in separate fresh directories with
    only cached input and `SAMPLE_SIZE=20_000`. This additionally checks the
    below-100k recipe path. No fitted estimators or workbooks were supplied.
  - [x] Desktop Chrome inspected all 11 pages: no table overflow in the 749-pixel
    reading column, visible shared helper definitions, broken images, missing
    alt text, or MathJax errors. Reviewed representative screenshots. Local link,
    fragment, and image-target checks passed. Generated outputs remain ignored.
  Full sequential rendering and independent chapter execution are distinct checks;
  independent execution was checked for the three recipes above, not every page.
  Cached input was reused; a fresh OpenML download and deployment were not tested.
  The Pages workflow runs after pushes to main, not as a pre-merge gate.
  Handoff: this requested revision is complete; M15 remains next.

- ☑ **M24 — ordered tutorial series** — converted `examples/` into a numbered
  Quarto book: `_quarto.yml` declares index, portfolio, experiments,
  diagnostics, scoring and tariff, reporting and operations, frequency–severity,
  tuning, temporal stability, protected-group audit, and manual tariff recipes.
  A shared `_shared.qmd` include (hidden cells) carries imports, the
  deterministic fetch/clean/cache loader, config builders, a local MLflow
  helper, and `holdout_diagnostics`; chapters refit their own models — only the
  pinned OpenML parquet caches persist. New executable coverage: `tune_experiment`
  with a 100k-row subset (outer holdout untouched), synthetic
  `temporal_split`-backed `stability_table`, a `protected_cols` subgroup audit,
  and `extract_tariff`/`apply_tariff`/`recalibrate_for_total` recipes. Completed
  2026-09-11: `just check` passed Ruff, Ty, and 680 tests (4 upstream skips);
  `just docs-build` strict-green; `just demo` rendered all 11 pages in ~11
  minutes; visual check of the lift/calibration grid passes; the tutorial-cell
  test in `tests/test_workflow.py` now binds to the chapter structure.
  `docs/guide/fremtpl2.md` is the series hub; README, installation, migration,
  PRD §3/§9/§10, AGENTS, justfile, CI docs workflow, and `.gitignore` updated.
  Generated `_book/` and artifacts stay ignored. Handoff: M15 stays next.
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
  GitHub Releases and PyPI trusted publishing, after M16–M39 are green and
  the separate review is complete. Follow **Current focus**; recording this
  plan does not authorize publication.
- ☑ **M16 — preserve the experiment holdout** — immutable fit/test positions
  reused by tutorial diagnostics, training calibration, and CLI distillation.
- ☑ **M17 — reject inconsistent frequency-severity outcomes** — issue 2.
- ☑ **M18 — faithful tariff bins and similarity groups** — issues 3 and 4.
- ☑ **M19 — complete missing-value diagnostics** — issues 5 and 6.
- ☑ **M20 — valid diagnostic references and residual scales** — issues 7, 9, and 12.
- ☑ **M21 — correct actuarial explanations** — issues 8, 10, 11, and 13.

- ☑ **M22 — show what fitted preprocessing does**.
- ☑ **M23 — evaluate the exported tariff against claims**.

- ☑ **M34 — estimator schema, targets, and scoring weights**.
- ☑ **M35 — configuration, preprocessing, and input inspection**.
- ☑ **M36 — training-only tariff calibration**.
- ☑ **M37 — stable tariff arithmetic and literal workbook labels**.
- ☑ **M38 — complete and unambiguous diagnostics**.
- ☑ **M39 — reproducible results and comparable evaluation**.
  Scope and acceptance checks are in the source audit remediation plan above.

## Earlier remediation status (historical)

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
- Historical M23 handoff: **M15** repeats distribution and isolated CLI checks
  before publication. The current tutorial improvement order above supersedes
  that next-session instruction.

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
