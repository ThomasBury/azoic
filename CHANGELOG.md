# Changelog

## Unreleased

- Replace README and documentation branding with the new Azoic banner, logo and
  icons; keep four README badges for PyPI, documentation, CI and license.

## 0.6.0 — 2026-11-12

This minor release collects the changes since 0.5.0. It adds an explicit path
from development experiments to reviewed tariffs and production handoffs.
The package remains pre-1.0; the compatibility changes below follow Azoic's
policy of reserving incompatible public changes for minor releases.

### Save, review and hand over fitted tariffs

- Reserve final-test records by ID before experimentation with `split_portfolio`.
  `check_experiment` and `azoic check` validate explicit predictor configurations
  without fitting, repairing data or applying claim caps.
- Save and load fitted candidates with their configuration, preprocessing,
  versions and development membership. Saved prediction, comparison, reporting
  and direct GLM export do not fit models again. Portfolio frames are excluded.
- Keep approved numeric bins and typed category groups fixed through refits.
  Revise GLM tariff factors separately from the fitted model, recording reasons,
  original factors and one optional training calibration multiplier.
- Produce a tariff-review report with complete CSV evidence and incumbent-rate
  comparisons aligned by unique record ID. Selection and rationale remain
  explicit human decisions.
- Evaluate a selected frozen fit on reserved final records, then explicitly
  refit production on the original full portfolio. Keep final evidence attached
  to the evaluated predecessor, separate from full-training production metrics.
- Export a versioned production bundle containing the workbook, specification,
  trusted Python artifact, batch-scoring recipe and synthetic agreement cases.
  The workbook bundle requires an exportable log-link GLM.

### Modelling, diagnostics and reliability

- Learn numeric bins and categorical groups using univariate LightGBM trees,
  with native missing routing, credibility floors and inspectable mappings.
  Quantile binning and rare-level grouping remain explicit alternatives.
- Add per-model preprocessing, in-memory experiment input, feature screening
  controls and recorded constructor/runtime/tuning provenance.
- Improve outcome and shape validation, temporal category ordering, zero-weight
  ranking behavior and double-lift weighting. Errors identify columns and a
  bounded sample of row positions rather than displaying portfolio values.
- Reject unsupported export transformations before opening workbooks. Replace
  destinations only after successful saves and preserve existing permission bits.
- Reduce tuning overhead and vectorize native preprocessing lookups. Linux
  million-row measurements and their hardware/memory limits are recorded in
  [the archived M62 record](https://github.com/ThomasBury/azoic/blob/main/development/archive/M62_VALIDATION.md);
  they are not a general runtime promise.

### Compatibility and migration

- The default tree binning and similarity grouping now require outcomes and
  can produce different mappings. Native tree intervals use upper-inclusive
  thresholds (`<=`); manual/quantile intervals are lower-inclusive. Changed tree
  mappings require explicit missing destinations. Refit and review affected tariffs.
- Invalid `RiskGBM` powers and monotonic controls raise during `fit`, including
  after `set_params`, rather than during construction. Move corresponding error
  handling to the fitting call.
- Run/result records and comparison/report schemas include additional provenance,
  revision and evidence fields. Fixed-schema consumers must accept those additions.
  Final-evaluation evidence and production `_full` metrics have distinct meanings.
- Saved artifacts are trusted same-code/environment pickle, not a portable format.
  Do not assume that artifacts saved under 0.5.0 can be loaded under 0.6.0.
- Dependency floors are now glum 3.4.1, Typer 0.27.1 and openpyxl 3.1.5.
  Python 3.12+ remains supported in metadata; full checks use locked Python 3.12
  dependencies, with separate installed-artifact checks for low direct versions
  and Python 3.14.
- The documented first-model starter remains pinned to published 0.5.0 and is
  also tested against the checkout. This release draft does not change that
  starter's Python or YAML examples.

### Documentation and remaining evidence

- Bundle three version-matched user skills for modelling, diagnostics and tariff
  work, with self-contained API references and Library Skills installation guidance.
  Keep diagnosis/export separate from fitting and calibration, and final evidence
  separate from production training. Copies require refreshing after package updates.
- Expand source-to-target accounting and missing-cost/claim-cap sensitivity in
  the freMTPL2 portfolio chapter without changing its loader rules.
- Replace the manual-tariff recipe with a review of an exported GBM-derived tariff:
  pool two age relativities, separate distillation from adjustment cost, and
  compare fidelity, claims fit, premium redistribution and illustrative loss ratios.
- Practitioner handoff observation, independent maintainer/professional review,
  receiving-engine agreement and deployment acceptance remain separate evidence.
  Scripted checks and historical capped claims do not establish those outcomes.

[Changes since 0.5.0](https://github.com/ThomasBury/azoic/compare/v0.5.0...HEAD)

## 0.5.0 — 2026-10-17

First PyPI release. The earlier GitHub `0.4.1` release did not reach PyPI
because its trusted publisher was not configured. This release includes the
following changes since that tag; the old tag remains intact.

### Correctness and input contracts

- Preprocessing rejects missing or infinite supplied outcomes, including numeric
  strings that convert to nonfinite values. Unknown outcomes no longer become
  zero claims; refit affected models from valid outcomes.
- Monotonic binning handles constant/tied predictors and empty bins. Both
  transformers raise when scoring input cannot match fitted mapping columns,
  including incompatible switches between named DataFrames and arrays.
- Estimators validate numeric predictors, one-dimensional rate targets, scoring
  weights, configured exposure columns, and objective names. Explicit sample
  weights still override exposure weights where supported.
- Exposure must represent at least one day (1/366 year, with day-count tolerance)
  at portfolio, model, preprocessing, diagnostic, and tariff boundaries. Explicit
  sample weights remain exempt; zero-weight rows remain legal for ranking curves.
- Preprocessing validates configured weights and mapping overrides, preserves
  fitted state after invalid overrides, and merges undersized final bins.
- Frequency-severity YAML forwards supported parameters and rejects conflicting
  special columns. Relative data paths resolve beside their YAML file.
- Calibration retains complete groups of tied predictions and genuine missing
  levels. Diagnostics validate inputs rather than silently dropping bad values.
- Run records preserve fitted inputs/configuration snapshots; comparisons flag
  incompatible runs. MLflow logs the applied configuration.
- Tariff recalibration uses training data; exports preserve fitted GLM behavior,
  stable reference levels and columns, and safely encode spreadsheet labels.
  Plotting and feature profiling reject invalid input at their boundaries.

### Dependencies and installation

- Requires Python 3.12+, pandas 3.0+, and scikit-learn 1.6+.
- GLM, GBM, and frequency-severity models support pandas `str`, nullable `string`,
  and `object` predictors without changing caller frames.
- Install with `uv add azoic==0.5.0` or `python -m pip install azoic==0.5.0`.
  AWS, MLflow, tuning, and interactive plotting remain optional extras.

### Documentation and release validation

- The freMTPL2 tutorial is now an executable book with a main modelling/scoring
  path and optional reporting, frequency-severity, tuning, temporal, protected
  group, and manual-tariff recipes.
- Installation, first-model, configuration, scoring, calibration, and export
  guidance now describe the implemented contracts.
- PR CI validates lint, production types, tests, strict documentation, and
  isolated wheel/source-distribution installs. Main pushes execute the full
  real-data tutorial and deploy Pages.
- Release publication uses PyPI trusted publishing from validated artifacts.
  Installed-package checks cover model fitting, preprocessing regressions,
  version agreement, and all five CLI commands; release tags must match versions.

[All changes since 0.4.1](https://github.com/ThomasBury/azoic/compare/0.4.1...v0.5.0)
