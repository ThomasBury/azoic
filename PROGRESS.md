# Azoic — Progress

> Living tracker. Mirrors `PRD.md` section 6 milestones. Update after every
> chunk of work.

Legend: ☐ pending · ◐ in progress · ☑ done

> Implement exactly one pending milestone per session. Mark it ◐ before implementation, run its acceptance checks, mark it ☑ only when green, then stop with a handoff. Do not start the next milestone automatically.

## Current focus

- **Goal:** make the existing tutorial understandable and adaptable by a pricing
  analyst comfortable with Python DataFrames and train/test separation, without
  assuming prior Azoic, GLM/GBM, Quarto, or MLflow experience.
- **Active milestone:** none. **Next task: M15 release review, in a separate session.**
- **Delivery order:** M25 → M26 → M27 → M28 → M29 → M30; then return to the
  separate M15 release handoff. Publication is outside this tutorial plan.
- **State:** M25 completed on 2026-09-13; M26–M30 completed on 2026-09-14.
  All six tutorial milestones are green. The
  review found broad feature coverage but weak adaptation and worked-decision
  examples. This plan improves the existing book, not the library's public API.
- **Review baseline:** `just check` passed Ruff/Ty and **682 tests, 4 upstream
  skips**. All ten chapter sources were reviewed; representative existing
  rendered outputs were inspected. No fresh book render or OpenML download was
  performed during the review. These are baseline results, not milestone acceptance.
- **Plan verification (2026-09-13):** after saving the plan, `just check`
  passed Ruff/Ty and **682 tests, 4 upstream skips**; `git diff --check`
  passed. This session changed only `PROGRESS.md`, `PRD.md`, and `AGENTS.md`;
  no implementation milestone was started and no tutorial render was needed.
- **Resume here:** inspect `git status --short`, read M30's completion checkpoint
  and M15's release requirements. Repeat distribution builds and isolated CLI
  checks on the corrected source before any publication decision. The working tree already
  contains substantial tutorial and library edits; preserve them.

This section and the delivery order below supersede historical statements that
M15 is next. Completed milestones and their evidence remain historical records.

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
  GitHub Releases and PyPI trusted publishing, after M16–M30 are green.
  Follow **Current focus**; this tutorial plan does not authorize publication.
- ☑ **M16 — preserve the experiment holdout** — immutable fit/test positions
  reused by tutorial diagnostics, training calibration, and CLI distillation.
- ☑ **M17 — reject inconsistent frequency-severity outcomes** — issue 2.
- ☑ **M18 — faithful tariff bins and similarity groups** — issues 3 and 4.
- ☑ **M19 — complete missing-value diagnostics** — issues 5 and 6.
- ☑ **M20 — valid diagnostic references and residual scales** — issues 7, 9, and 12.
- ☑ **M21 — correct actuarial explanations** — issues 8, 10, 11, and 13.

- ☑ **M22 — show what fitted preprocessing does**.
- ☑ **M23 — evaluate the exported tariff against claims**.

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
