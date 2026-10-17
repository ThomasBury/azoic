# Preprocessing fixes and release plan

Status: M45 merged in [PR #1](https://github.com/ThomasBury/azoic/pull/1).
M15 completed 2026-10-17: `azoic==0.5.0` is public on PyPI.
Plan recorded 2026-10-16; execution evidence lives in `PROGRESS.md`.
Delivery order: **M45 → M15**, one milestone per implementation session.
This plan authorizes no implementation, Git delivery, private configuration,
tagging, or publication by itself.

## Evidence from the review

Reviewed commit: `73874e5491d196466c782e49a7ba8cae1d5c2b4b`.
Reproductions used NumPy 2.5.2, pandas 3.0.6, scikit-learn 1.9.0, and SciPy 1.18.0.
The three findings are confirmed in `src/azoic/preprocessing.py`:

| Finding | Reproduced behavior | Scope |
|---|---|---|
| 3 — missing outcomes become zero risk | Tree fitting with a missing target produced the same boundary, `[1.5]`, as an explicit zero. A category with all outcomes missing received aggregate claims 0 over exposure 4. | `target_col` bypasses outcome validation. Numeric `y` rejects NaN/infinity, but strings such as `"nan"` pass initial validation before conversion. `run_experiment` separately validates portfolio outcomes. |
| 4 — monotonic binning crashes on ties | Four identical predictor values and `[1, 1, 2, 2]` raised `Weights w must be strictly positive`, in both monotonic directions, with and without exposure weights. | Quantile boundaries create empty bins; their zero weights reach isotonic regression. |
| 5 — representation changes skip transformation | Both transformers returned ages `[10, 20, 30, 40]` unchanged after fitting a named DataFrame and transforming its array. Array fitting followed by named DataFrame transformation also skipped the fitted mapping. | A sklearn warning precedes the transform loop silently skipping unmatched column names. |

Review baseline: `just check` passed Ruff, Ty, and **1055 tests**, with **4 skips
and 2 expected failures**, in **228.22 s**. Existing tests do not catch these bugs.
The ARFS comparison was not verified. Temporary review logs are not durable
project artifacts; this document preserves the relevant results.

## M45 — preprocessing correctness

### Fix 3: reject unknown supplied outcomes

- Trace `_column_array`, `_resolve_target`, both `fit` methods, and their callers
  before editing. Reuse public sklearn validation and existing local helpers.
- Validate supplied outcomes after numeric conversion, before predictor masking
  or learning either partition. Reject NaN and positive/negative infinity,
  including partial and entirely missing targets. Validate the resolved values
  used for learning so unit conversion cannot introduce nonfinite outcomes.
- Remove tree-target zero substitution and the fallback to quantiles when a
  supplied target is entirely missing. Preserve existing behavior when no target
  is supplied and the selected strategy permits unsupervised fitting.
- Preserve `target_col` precedence and the existing fallback to `y` when that
  column is absent. Aggregate claims remain aggregate in grouping; binning uses
  rates, with exposure retained as weight. Missing predictors remain legal.
- Regress both transformers, both outcome routes, NaN/±infinity, numeric strings,
  partial/all missing targets, and nullable pandas values. Retain existing
  exposure-unit and target-fallback checks.

### Fix 4: pool only occupied bins

- Remove empty bins before fitting isotonic regression, retaining their original
  positions so surviving boundaries refer to the correct original edges.
- A constant observed predictor yields no finite boundaries: one observed-value
  interval plus the reserved missing category. Do not invent positive weights
  for empty bins or replace the existing isotonic solver.
- Keep the correction local to monotonic pooling. Do not change
  `_weighted_quantile_edges`, which also serves stratification.
- Regress constant/tied predictors and empty interior bins, both directions,
  weighted/unweighted inputs, resulting boundary positions, and missing-predictor
  handling. Preserve credibility-floor behavior and ordinary monotonic results.

### Fix 5: fail when the fitted mapping cannot be applied

- Choose an explicit, actionable `ValueError` when fitted mapping columns cannot
  be matched to transform input. Check before applying mappings; remove the silent
  skip. Positional name restoration is not needed for this fix.
- Cover both representation-switch directions in both transformers. Preserve
  DataFrame-to-DataFrame and array-to-array behavior, passthrough columns,
  categorical vocabularies, and deliberate omissions through `set_mapping`.
- Document the input contract in transformer docstrings and the preprocessing
  guide. A generic sklearn warning alone does not satisfy the contract.

### Scope and acceptance

Primary edits belong in `src/azoic/preprocessing.py`,
`tests/test_preprocessing.py`, and `docs/guide/data-preprocessing.md`.
Inspect `PreprocessingSpec.build_steps`, sklearn pipelines, tutorial assembly,
and tariff extraction, which applies preprocessing through `_pipeline_parts`.
Use existing workflow, tutorial, and tariff checks; add integration coverage only
where a changed contract is not already exercised. No new dependency, module,
compatibility shim, or validation framework is planned.

- [x] Mark M45 ◐ before implementation; leave M15 pending.
- [x] Add focused regressions and demonstrate the reported failures before fixing.
- [x] Complete all three fixes and their documentation.
- [x] Run `uv run pytest tests/test_preprocessing.py -x`.
- [x] Run `just check`, including existing workflow/tutorial/tariff checks.
- [x] Run `just docs-build` and verify changed local references.
- [x] Run `git diff --check` and review the full diff for unrelated changes.
- [x] Record actual checks/results, mark M45 ☑ only when green, then stop.

Completed locally on 2026-10-17: 64 focused cases and 279 preprocessing tests
passed (2 upstream skips). Full `just check` passed Ruff/Ty and 1119 tests
(4 skips, 2 expected failures); strict docs, rendered contracts, guide links,
formatting, and diff review passed. See the M45 completion checkpoint in
`PROGRESS.md` for evidence. Git delivery merged in [PR #1](https://github.com/ThomasBury/azoic/pull/1);
its timeline records review, CI, merge, and branch cleanup outcomes.

## Fix PR

Proposed branch: `fix/preprocessing-contracts`.
Proposed title: `fix: validate preprocessing outcomes and prevent skipped transforms`.

Keep one focused PR, with three reviewable commits containing their own tests:

1. `fix: reject nonfinite preprocessing outcomes`
2. `fix: handle empty bins in monotonic pooling`
3. `fix: reject unmatched preprocessing input columns`

Include the corresponding documentation and milestone records with these changes.
The PR description should explain the three before/after cases, the deliberate
representation error, and validation actually run. Identify that previously
accepted unknown outcomes now raise and that affected models need refitting
from valid outcomes. Do not describe all-missing outcomes as zero claims.
Keep version changes and publisher configuration in the separate release unit.
The 2026-10-17 delivery request authorizes staging, conventional commits, push,
a labelled PR, Codex bot review, fixes, merge, and branch removal. CodeRabbit
is not a merge gate. This supersedes the planning-only authorization boundary.

## M15 — release reconciliation and publication

### Observed release state, 2026-10-16

- GitHub has a published [`0.4.1` release](https://github.com/ThomasBury/azoic/releases/tag/0.4.1),
  dated 2026-09-06, at `a3f242449be7db071a9f26238985a4015b7edf8a`.
- Its [release run](https://github.com/ThomasBury/azoic/actions/runs/34049504755)
  passed the build job and failed the publishing job with
  `invalid-publisher`: a valid token matched no configured publisher.
- The public `https://pypi.org/pypi/azoic/json` lookup returned HTTP 404.
  Recheck this before release; the lookup does not inspect private PyPI settings.
- Current metadata still says `0.4.1`, while main contains substantial changes
  beyond that tag, including pandas ≥3.0 and scikit-learn ≥1.6 requirements.
  Preserve the existing tag and release history.

### Release preparation PR

Recommended candidate: **0.5.0**, tag **v0.5.0**, reflecting the accumulated
contract and dependency changes. This is a planned candidate, not a version
change made by this session; finalize it in the release PR after reviewing the
full diff from `0.4.1` to the release candidate.

- [x] Start M15 only after M45 is green and delivered.
- [x] Refresh public release/PyPI state and reconcile the tracker with it.
- [x] Prepare `chore: prepare 0.5.0 release` as a separate PR. Align
  `pyproject.toml`, `src/azoic/__init__.py`, and the local project entry in
  `uv.lock`; update installation guidance, release notes, and milestone records.
- [x] Explain the complete release delta, including stricter outcome/input
  contracts, raised dependency requirements, and the three preprocessing fixes.
- [x] Verify the PyPI trusted publisher matches project `azoic`, GitHub owner
  `ThomasBury`, repository `azoic`, workflow `release.yml`, and environment
  `pypi`. Correct private settings only with separate authorization. The existing
  workflow already uses a publishing job with `id-token: write`; do not add
  credentials or another release workflow to work around the identity mismatch.
- [x] Run locked all-extras/groups sync, `just check`, and strict docs.
- [x] Build fresh wheel/sdist artifacts into a clean temporary output directory.
  Reuse `tests/smoke_distribution.py` and CLI checks outside the checkout against
  each exact artifact; verify version and all five CLI commands. Exercise the
  focused preprocessing regressions against the installed artifacts as well.
- [x] Record candidate commit, artifact hashes, check results, remaining blockers,
  and concrete release notes before publication.

### Delivery decision — 2026-10-17

Live checks still show GitHub release `0.4.1` and HTTP 404 for the PyPI project.
Main is 28 commits ahead of that tag before M45. No additional pending RXX
prerequisite was found; M15 is next after M45 delivery. Keep the candidate
`0.5.0` version bump in its separate release PR so the full accumulated delta,
installed artifacts, and release notes are reviewed together. Do not tag M45
as another `0.4.1` release or rerun the old publishing job.

The user reports configuring the PyPI trusted publisher; its private settings
have not been independently verified. The repository has a `pypi` environment
and the existing workflow already isolates OIDC permission to the publish job.
The same request authorizes subsequent GitHub tagging/release and PyPI
publication after the separate M15 release PR is merged and its checks pass.
Retain that authorization; ask only if a new action exceeds its scope.

### Authorized publication and completion

- [x] After the release PR is merged and its exact commit has green CI,
  confirm the recorded authorization covers tagging/publication/private changes.
- [x] Create `v0.5.0` at that commit and publish its GitHub release through the
  existing `.github/workflows/release.yml` flow. Do not retry the old release to
  publish the old source or move its tag.
- [x] Confirm release build and publishing jobs succeed. Verify the published
  package and hashes, then perform a fresh isolated PyPI install, version check,
  preprocessing smoke, and all five CLI command checks.
- [x] Confirm the documentation/Pages workflow is green. Mark M15 ☑ only after
  successful PyPI publication and post-publication checks; otherwise record the
  failed step and keep the milestone incomplete. Fix a published defect through
  a new version rather than rewriting release history.

## Handoff

M45 merged in PR #1. M15 completed 2026-10-17 through release PR #2:
[`v0.5.0`](https://github.com/ThomasBury/azoic/releases/tag/v0.5.0) and
[`azoic==0.5.0`](https://pypi.org/project/azoic/0.5.0/) are public. All acceptance
items above are green, including published hashes/provenance, fresh registry
install, preprocessing, all five CLI commands, first model, and Quarto/Pages.
Read `PROGRESS.md` Current focus and the M15 completion checkpoint for exact
commits, workflow links, and hashes. Preserve existing tags and published
artifacts. Finish the documentation-only completion record, then stop; no next
milestone has been selected.
