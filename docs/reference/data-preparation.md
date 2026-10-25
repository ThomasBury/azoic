# Data and preparation API

!!! note "Unreleased checkout documentation"

    This page describes the current source checkout; some APIs differ from the
    published 0.5.0 package. For a release-compatible journey, start with the
    [first model](../getting-started/first-model.md). See
    [installation](../getting-started/installation.md) for the version boundary.

Use these APIs to validate a Parquet data contract, review feature quality,
learn inspectable mappings, and create leakage-safe split labels. The
[data profiling and preprocessing guide](../guide/data-preprocessing.md)
shows the task flow before the generated signatures below.

| Module | Public API | Purpose |
|---|---|---|
| `azoic.data` | `DatasetSpec`, `load_data`, `split_portfolio` | Special-column contract; Parquet loading with contract validation |
| `azoic.profile` | `profile_features`, `screen_features` | Per-column screening stats; recommended keep/drop/group actions |
| `azoic.preprocessing` | `AutoBinner`, `AutoGrouper` | Inspectable numeric binning and categorical grouping transformers |
| `azoic.validation` | `make_strata`, `temporal_split` | Exposure-balanced stratum labels; leakage-safe temporal split |

::: azoic.data

::: azoic.profile

::: azoic.preprocessing

::: azoic.validation
