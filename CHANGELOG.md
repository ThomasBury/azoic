# Changelog

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
