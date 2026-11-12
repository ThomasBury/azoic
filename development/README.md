# Maintenance and current work

This page is the sole current-status authority. For setup and checks, use
[CONTRIBUTING](../CONTRIBUTING.md); for durable contracts, use [design](design.md).
Read historical records only when their evidence is needed.

## Current focus

- **0.6.1 delivery ◐** — authorized on 2026-11-12: stage the documentation,
  branding and license changes, create a labelled PR with Conventional Commits,
  obtain Codex review, address findings and publish the reviewed patch release.
  Keep the PR open; CodeRabbit may be skipped only if its credits are exhausted.
- **Branding replacement ☑** — completed on 2026-11-12: README banner and four-badge
  row, docs logo and favicon use the supplied assets. Strict docs, local rendered
  previews and contributor checks passed; artwork and unrelated work are preserved.
- **Repository documentation consolidation ☑** — completed on 2026-11-12.
  Existing uncommitted work and historical evidence are preserved. No further
  product milestone or release is selected as part of this cleanup.
- **M62 ◐ — performance and observed handoffs:** engineering measurements and
  session preparation passed; all four actual practitioner observations remain
  pending. No practitioners have been observed. Resume only with real participants;
  scripted runs, agent trials and maintainer walkthroughs cannot complete M62.
- **Release baseline:** Azoic 0.6.0 was published on 2026-11-12 from `502766b`
  after PR #26, with `openpyxl>=3.1.5`. M64 skills and their Linux-link/Windows-copy
  checks completed; M63 tutorial and M56–M61 implementation completed. These are
  recorded historical results, not checks rerun by this cleanup.

## Unfinished evidence and boundaries

| Obligation | Status and next action |
| --- | --- |
| M62 practitioner acceptance | Recruit two medior actuaries, one senior actuary and one ML engineer; run the chain below, repair blockers and repeat failed tasks. |
| M54/M55 independent maintainability | Obtain an independent maintainer's unaided installed-package [component recipe](../docs/reference/compatibility.md) reproduction and report ambiguities. Single-agent extension exercises are not independent evidence. |
| M47/M48 actuarial review | Obtain professional review and predictive comparisons of portfolio selection/target sensitivity; retain unresolved source-definition questions and missing-cost assumptions. Accounting checks alone cannot resolve them. |
| External engine/deployment | Real receiving-engine agreement, deployment and rollback remain downstream evidence; synthetic agreement tests do not establish readiness. |

Conditional features in [design](design.md#deferred-and-demand-gated-work) are
not scheduled milestones. No next product milestone is selected; the 0.6.1
maintenance release above is explicitly authorized.

## M62 observation protocol

### Preparation

Obtain agreement to observation/recording. Use anonymous participant IDs and keep
contact details separate. Use a clean directory for each attempt and record the
same checkout/lock/environment. Install dependencies beforehand; separately record
participant setup. Normal documentation/search/CLI help is allowed. Assistance by
an AI, colleague or facilitator makes the attempt assisted, not unaided acceptance.

Use the synthetic [first-model recipe](../docs/getting-started/first-model.md).
The facilitator may generate a pristine `portfolio.parquet` in advance but must
not supply its fitted outputs as participant work. Medior A starts with the recipe;
Medior B with the pristine portfolio. Declare stable IDs and reserve final periods
[before experimentation](../docs/guide/actuarial-workflow.md#freeze-portfolio-membership-before-experimenting).
Supply a synthetic incumbent rate of 400 EUR/year per development ID, with one
zero rate, explicitly as a comparison assumption. Preserve full frames, indices
and dtypes for fingerprint checks; use new output directories.

The senior receives Medior B's original/revised candidates, original development
frame and review bundle without final outcomes. The engineer receives the selected
frozen saved artifact, unchanged development/final frames, predeclared membership
and selection reasons. An upstream failure blocks the downstream chain; a facilitator
substitute can support a separate attempt but cannot pass the end-to-end handoff.

Explain only task outcomes and supplied inputs before starting. Record elapsed
and active minutes, breaks, abandoned work, errors, misunderstandings and exact
interventions. Schedule up to 90 minutes per medior/engineer task and 60 minutes
for senior review; these are session limits, not speed targets. A timeout is
unfinished. Observe without hints and capture explanations before correcting them.

### Tasks and acceptance

1. **Medior A:** fit/compare the GLM and raw GBM; hand over diagnostics, rates
   and an Excel tariff. Unaided, explain predictors, exposure weighting, rate
   versus period cost, ranking versus O/P, and workbook recalibration. The
   recipient must reproduce rates; synthetic results do not prove model superiority.
2. **Medior B:** save final membership before experiments; check explicit YAML
   predictors; fit/save candidates and resume scoring/comparison/export. Change
   one age boundary with a fixed native mapping and refit a separate candidate.
   Override a factor with a reason and one recorded training calibration. Deliver
   original/refitted/revised candidates and incumbent review. Pass only with final
   rows unused, sources preserved, identical report IDs/basis, matching workbook/
   Python rates, and a correct explanation of which operations fit or recalibrate.
3. **Senior actuary:** without the author/notebook, explain rate changes, affected
   groups, exposure/claims support, candidate scales, zero-incumbent percentages,
   uncertainty and missing evidence. Select with retained-table rationale or reject
   with justification. Rejection may pass review but blocks production approval;
   development comparisons must not be described as independent final evidence.
4. **ML engineer:** in a fresh process, load/score outcome-free quotes; evaluate
   the frozen selection once on reserved final membership; explicitly refit the
   exact original full-portfolio union. Export a new production bundle and run
   its batch recipe. Check unrounded rates, exact/adjacent boundaries and missing/
   unseen rejections. Keep predecessor final evidence attributed to the frozen fit,
   production metrics full-training only, and explain trusted pickle/environment
   limits plus deployment/rollback ownership. Python agreement is not engine agreement.

Use the [configuration](../docs/guide/experiment-configuration.md),
[preprocessing](../docs/guide/data-preprocessing.md) and
[operations](../docs/guide/operations.md) guides for these tasks.

### Evidence and repair

Store outputs, terminal logs, revision/versions and event CSVs under ignored
`evidence/m62/`, one directory per anonymous participant/attempt:

```csv
participant_id,role,attempt,task,start_utc,end_utc,elapsed_minutes,active_minutes,outcome,help,misunderstanding,evidence_path,blocker,next_action
```

Record actions/errors and exact messages without portfolio values, recovery time,
help and short verbatim explanations. Outcomes are `unaided-pass`, `assisted`,
`unfinished` or `blocked`. Keep failed and assisted attempts. Summarize by role,
link blockers to minimal fixes/focused checks, and repeat failed tasks, preferably
with fresh practitioners. Never silently upgrade an assisted attempt. M62 completes
only when all four unaided handoffs pass, blocking failures are resolved and
applicable project gates pass. Keep unobserved acceptance pending.

## Reproduce the M62 engineering measurement

After [contributor setup](../CONTRIBUTING.md#set-up-a-checkout), on Linux:

```bash
uv run python tests/benchmark_workflow.py --rows 1000000 --threads 1 --out /tmp/azoic-m62-million-1
```

Choose a new output directory; existing directories are rejected. The seeded
synthetic workload has 20 numeric/10 categorical predictors, compact levels,
no missingness, a native-preprocessed GLM and raw GBM. Fresh processes measure
fit/save and no-fit resume with prediction/report/workbook agreement checks.
Generation/imports/startup/verification are outside timed totals. Record hardware,
revision/status, versions, affinity and observed native/Arrow thread limits.
Stage RSS is sampled whole-process resident memory, not allocation deltas; report
kernel lifetime peak separately. Reads may use warm OS cache and desktop activity
is uncontrolled. Keep generated evidence outside Git. Use 500 rows for a quick
run or `uv run pytest tests/test_benchmark_workflow.py` for regression checks.

[Archived M62 methodology and results](archive/M62_VALIDATION.md) retain the full
measurement definitions, historical tables and limitations. Those measurements do
not cover tuning/FSM, large reviews, production-bundle performance, high cardinality,
missing-heavy portfolios or Windows performance. No runtime, memory or readiness promise follows.

## Latest checkpoint — 0.6.1 delivery — 2026-11-12

- [x] Inspect the complete branch diff, previous checks and remote delivery conventions.
- [x] Create topical Conventional Commits and reconcile package/skill versions.
- [x] Run locked checks, strict docs and installed wheel/sdist smokes.
- [ ] Open the PR with `documentation` and `release` labels; obtain bot review and repair findings.
- [ ] Publish tag `v0.6.1` and the GitHub release from the reviewed commit; verify publication.

0.6.1 preparation passed: `uv sync --locked --all-extras --all-groups --offline`,
`just docs-build`, Ruff, Ty and **1,517 tests** (4 skips, 2 expected failures,
21 warnings; 450.86 seconds). Focused version/skill tests also passed (8 tests).
The lockfile differs only in Azoic's version; every skill metadata version matches.
Fresh Linux/Python 3.12 wheel and sdist installations with locked runtime-only
dependencies passed `uv pip check` and the complete outside-checkout distribution
smoke, including all eleven CLI helps, packaged skills and workbook agreement.
Both artifacts include the MIT license; the wheel declares `License-Expression:
MIT` and `License-File: LICENSE`. A README-only rebuild preserves every tested
package file byte for byte. Runtime ASTs are unchanged except the version string.
All 161 local file/anchor/image-source references resolve, and pinned README asset,
license and contributor-guide targets exist in commit `1259918`.

Artifacts and isolated environments are under `/tmp/azoic-release-u1ycw8dh/`;
commands used `UV_CACHE_DIR=/tmp/azoic-doc-cleanup-uv-cache`. Prior rendered-preview
evidence is retained below. No tag or release exists yet. Next action: push the
release preparation, open the labelled PR and obtain Codex/CodeRabbit review and
remote CI before publication. M62 human acceptance stays pending.

## Previous checkpoint — branding — 2026-11-12

- [x] Inspect branding references, supplied assets and pre-existing uncommitted work.
- [x] Replace README/docs branding and reconcile asset guidance and changelog.
- [x] Check rendered images, README fallback, links and narrow-screen layout.
- [x] Run strict docs, full contributor checks and diff checks; record results.

`just docs-build` passed with no issues; `just check` passed Ruff, Ty and **1,517
tests** (4 skips, 2 expected failures, 21 warnings; 374.63 seconds). Both commands
used `UV_CACHE_DIR=/tmp/azoic-doc-cleanup-uv-cache`. Ten local headless Chrome
previews passed at 1280/375 px:
GitHub-style and actual PyPI-sanitized README markup in light/dark modes, plus
the built docs homepage at both widths. Images load at their original proportions
without horizontal overflow; the GitHub picture selects dark/light correctly and
PyPI retains the light fallback and four linked badges. Representative screenshots
were visually inspected. All 55 emitted branding image/favicon references and 160
local/GitHub-main file/anchor references resolve. All four public badge endpoints
returned SVGs. `git diff --check` passed; only the six intended files differ from
the pre-task snapshot, with artwork and unrelated work preserved.

Previews and the temporary verification script are under
`/tmp/azoic-branding-o5vpktvu/`; README previews map the future raw GitHub image
URLs to local supplied files. The shared browser host was unavailable; these are
local renders, not live GitHub/PyPI website previews. No branding acceptance
blockers remain. Changes are local and uncommitted. Next action: review/deliver
this branding change together with its supplied assets; the raw README image URLs
become available when the assets reach `main`. The current PyPI release description
stays unchanged until a separately authorized release. No product milestone,
release, deployment or repository-settings change is included; M62 remains pending.
Real-data tutorial renders and distribution smokes were not rerun.

## Previous checkpoint — documentation consolidation — 2026-11-12

- [x] Inspect current records, cross-references and pre-existing uncommitted work.
- [x] Archive the four original records; consolidate current status/design and entry points.
- [x] Reconcile retained rules/obligations, local links and obsolete references.
- [x] Run strict docs, full contributor checks and diff checks; record actual results.

Verification: `just docs-build` passed with no issues; `just check` passed Ruff,
Ty and **1,517 tests** (4 skips, 2 expected failures, 21 warnings; 367.27 seconds).
Commands used `UV_CACHE_DIR=/tmp/azoic-doc-cleanup-uv-cache` after the initial docs
attempt could not write to the sandbox's default uv cache. `git diff --check`
passed. All 160 local/GitHub-main file and anchor references resolve in the current
tree, and all 55 referenced rule-ownership test nodes exist. The four archives
preserve original content except notices/relocated links, all twelve actuarial
rules remain verbatim, unrelated tracked contents match the pre-cleanup snapshot,
and Python runtime ASTs are unchanged. No runtime/API/dependency changes were made.

Not rerun: real-data tutorial renders, distribution smokes, live remote links or
human observations. No cleanup acceptance blockers remain. Changes are local and
uncommitted. Historical evidence is in [PROGRESS](archive/PROGRESS.md), [PRD](archive/PRD.md),
[preprocessing/release plan](archive/PREPROCESSING_FIX_PLAN.md) and
[M62 validation](archive/M62_VALIDATION.md). Archived instructions/permissions
are not current authority. Next action: review/deliver this documentation change;
resume M62 only when actual participants are available. Do not start product
work, publish or deploy automatically.
