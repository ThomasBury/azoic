# Data and preparation API

Use these APIs to validate a Parquet data contract, review feature quality,
learn inspectable mappings, and create leakage-safe split labels. The
[data profiling and preprocessing guide](../guide/data-preprocessing.md)
shows the task flow before the generated signatures below.

| Module | Public API | Purpose |
|---|---|---|
| `azoic.data` | `DatasetSpec`, `load_data` | Special-column contract; Parquet loading with contract validation |
| `azoic.profile` | `profile_features`, `screen_features` | Per-column screening stats; recommended keep/drop/group actions |
| `azoic.preprocessing` | `AutoBinner`, `AutoGrouper` | Inspectable numeric binning and categorical grouping transformers |
| `azoic.validation` | `make_strata`, `temporal_split` | Exposure-balanced stratum labels; leakage-safe temporal split |

::: azoic.data

::: azoic.profile

::: azoic.preprocessing

::: azoic.validation
