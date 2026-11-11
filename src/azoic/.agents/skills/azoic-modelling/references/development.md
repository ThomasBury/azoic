# Separate, fit and save development candidates

Check the installed version as described in SKILL.md. Adapt column names and
model settings to the user's declared portfolio. The example uses unique
`record_id`, aggregate `claim_amount`, exposure in years, `period`, `driver_age`
and `region`. The user supplies `final-ids.json` as a JSON list declared before
experimentation. Do not choose final membership from observed model performance.

## Reserve membership once

Run this only when separating the original portfolio. Use a fresh output directory;
keep the exact saved frames, indices and dtypes for later fingerprint checks.
If development data is already separated, preserve its existing manifest instead.

```python
import json
from pathlib import Path

import pandas as pd
from azoic import split_portfolio

portfolio = pd.read_parquet("portfolio.parquet")
final_ids = json.loads(Path("final-ids.json").read_text(encoding="utf-8"))
development, final_test = split_portfolio(portfolio, final_ids, id_col="record_id")
with open("portfolio-membership.json", "x", encoding="utf-8") as stream:
    json.dump({"development": development.record_id.tolist(),
               "final_test": final_test.record_id.tolist()}, stream, indent=2)
development.to_parquet("development.parquet")
final_test.to_parquet("final-test.parquet")
```

## Fit only on development data

The workflow supplies rates and exposure weights internally. Tree mappings learn
on training rows. The raw GBM skips those mappings. Temporal splits preserve
equal timestamps; choose the split policy before comparing candidates.

```python
import pandas as pd
from azoic import (
    DatasetSpec, ExperimentConfig, ModelSpec, PreprocessingSpec,
    check_experiment, run_experiment, save_run,
)

development = pd.read_parquet("development.parquet")
config = ExperimentConfig(
    name="development-candidates",
    data_path="development.parquet",
    spec=DatasetSpec(target="claim_amount", exposure="exposure",
                     id_col="record_id", time_col="period", currency="EUR"),
    features=["driver_age", "region"],
    split="temporal",
    preprocessing=PreprocessingSpec(binner={"cols": ["driver_age"], "max_bins": 3}),
    models={
        "glm": ModelSpec(params={"family": "tweedie", "link": "log"}),
        "gbm": ModelSpec(kind="gbm", preprocess=False,
                         params={"n_estimators": 30, "n_jobs": 1, "random_state": 42}),
    },
)
checked = check_experiment(config, df=development)
run, estimators = run_experiment(config, df=development, return_estimators=True)
save_run(run, estimators, "candidates.pkl")
```

`check_experiment` validates without fitting or repairing. It requires explicit
predictors; put optional counts, protected fields, IDs, exclusions and basis
descriptions into `DatasetSpec`, not `features`. Descriptions record upstream
currency/valuation/adjustment choices, without changing the data.

`run.train_indices` and `run.test_indices` are positions in this development
frame; `run.record_ids` preserves their ID alignment. Inspect
`run.models[name].metrics`, `calibration_table` and the fitted preprocessing
before choosing a model. The workflow's `test` is development validation, not the
reserved final set. Preserve the original files, environment lock, config and
membership manifest alongside `candidates.pkl`. The pickle excludes portfolio
frames but includes IDs/learned state; it is not anonymized or portable.
