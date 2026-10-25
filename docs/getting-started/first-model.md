# First model

Fit a direct Tweedie generalized linear model (GLM) and a raw-feature gradient
boosting model (GBM), compare their diagnostics, then export the fitted GLM to
Excel. The only rating features are **driver age, vehicle age and region**.
Exposure is a weight; period controls the split; claim amounts and counts are
outcomes. None of those four columns is a rating feature.

This complete starter works with **Azoic 0.5.0 from PyPI** and with the checkout.
It creates synthetic data locally and needs no repository, test fixtures,
Quarto, optional extras or network after installation. It is a learning example,
not a reviewed production tariff.

!!! warning "The exposure convention"

    The target is `claim_amount / exposure`, a claim cost per year of exposure.
    Exposure travels inside `X` as the sample weight. Do not also use
    `log(exposure)` as an offset. Multiply a predicted rate by a policy's
    exposure to get its predicted cost for that period.

## Run the complete example

After [installing Azoic](installation.md#install-from-pypi), save the following
as `first_model.py` in your project directory. On Linux or Windows, run:

```bash
uv run python first_model.py
```

The script writes `portfolio.parquet`, two calibration PNGs and
`first-model-tariff.xlsx` in that directory. Rerunning replaces these example
outputs; use a separate directory from your own tariff files.

```python
from pathlib import Path

import numpy as np
import pandas as pd

from azoic.metrics import calibration_table, gini, mean_tweedie_deviance, op_ratio
from azoic.models import RiskGBM, RiskGLM
from azoic.plots import plot_calibration
from azoic.tariff import export_tariff
from azoic.validation import temporal_split

features = ["driver_age", "vehicle_age", "region"]

rng = np.random.default_rng(42)
n_policies = 5_000

exposure = rng.uniform(0.5, 1.0, n_policies)
driver_age = rng.integers(18, 90, n_policies)
vehicle_age = rng.integers(0, 25, n_policies)
region = rng.choice(["urban", "suburban", "rural"], n_policies, p=[0.4, 0.4, 0.2])
period = np.repeat(np.arange(24), np.ceil(n_policies / 24).astype(int))[:n_policies]

frequency = (
    0.10
    * np.where(driver_age < 25, 1.6, np.where(driver_age > 65, 1.3, 1.0))
    * np.where(region == "urban", 1.4, np.where(region == "rural", 0.6, 1.0))
    * (1.0 + 0.03 * vehicle_age)
)
claim_count = rng.poisson(frequency * exposure)
mean_severity = 2_500 * (1.0 + 0.02 * vehicle_age)
claim_amount = np.zeros(n_policies)
has_claim = claim_count > 0
claim_amount[has_claim] = (
    rng.gamma(3.0, mean_severity[has_claim] / 3.0) * claim_count[has_claim]
)

portfolio = pd.DataFrame(
    {
        "period": period,
        "driver_age": driver_age,
        "vehicle_age": vehicle_age,
        "region": region,
        "exposure": exposure,
        "claim_count": claim_count,
        "claim_amount": claim_amount,
    }
)

# Explicit categories also work on the released package.
portfolio["region"] = pd.Categorical(portfolio["region"])
portfolio.to_parquet("portfolio.parquet", index=False)
train_idx, test_idx = temporal_split(portfolio, "period", test_size=0.2)
train = portfolio.iloc[train_idx]
validation = portfolio.iloc[test_idx]
model_columns = features + ["exposure"]
y_train = train["claim_amount"].to_numpy() / train["exposure"].to_numpy()
actual = validation["claim_amount"].to_numpy()
weight = validation["exposure"].to_numpy()

models = {
    "glm": RiskGLM(
        family="tweedie", link="log", exposure_col="exposure",
        tweedie_power=1.5, random_state=42,
    ),
    "gbm": RiskGBM(
        objective="tweedie", exposure_col="exposure",
        tweedie_variance_power=1.5, n_estimators=50, num_leaves=15,
        learning_rate=0.05, random_state=42, n_jobs=1,
    ),
}
predictions = {}
rows = []
for name, model in models.items():
    model.fit(train[model_columns], y_train)
    prediction = model.predict(validation[model_columns])
    predictions[name] = prediction
    rows.append({
        "model": name,
        "validation_gini": gini(actual, prediction, weight),
        "validation_op": op_ratio(actual, prediction, weight),
        "validation_deviance": mean_tweedie_deviance(
            actual / weight, prediction, sample_weight=weight, power=1.5,
        ),
    })
    calibration = calibration_table(actual, prediction, weight, n_bins=10)
    print(f"\n{name} validation calibration (raw fitted rates)")
    print(calibration.round(3).to_string(index=False))
    plot_calibration(calibration, path=f"first-model-{name}-calibration.png")

# Export the same fitted GLM, with no change to its rate level.
tariff_path = export_tariff(
    models["glm"], Path("first-model-tariff.xlsx"), recalibrate=False,
)
diagnostics = pd.DataFrame(rows).set_index("model")
print(f"\ntrain rows: {len(train):,}; validation rows: {len(validation):,}")
print(f"period boundary: {train['period'].max()} < {validation['period'].min()}")
print(diagnostics.round(3).to_string())
print(f"wrote {tariff_path.resolve()} (raw GLM rates, no recalibration)")
```

`temporal_split` keeps earlier periods for training and later periods for
validation, without splitting equal timestamps. Missing periods are rejected.
Here the later periods are **development validation**: if you change the model
after reading these results, they cannot also be an untouched final test.
Real work needs a separate final-test portfolio reserved before model selection.

## Read the result

| Output | Question it answers | How to read it |
| --- | --- | --- |
| Validation Gini | Does the model rank risk? | Higher indicates better concentration on these rows; it does not establish calibration. |
| Validation O/P | Is the overall rate level right? | Observed claims divided by predicted claims: 1 is balance; 1.24 means claims were about 24% above predictions. |
| Validation deviance | How well do the predicted rates fit? | Lower is better on the same observations, exposure weights and power (here 1.5). |
| Calibration table/chart | Where does the rate level miss? | Inspect risk groups, their exposure and distance from observed rates, even when total O/P is near 1. |

The GLM uses one linear driver-age effect on the log scale; the generator raises
risk at both young and older ages. The raw GBM can learn nonlinear effects
without binning first. That difference motivates a comparison; a small synthetic
validation sample cannot establish that either model is superior for your book.
Sparse segments deserve less confidence than exposure-heavy ones.

Predictions and calibration outputs use **raw fitted pure-premium rates**.
The workbook contains the GLM's `base_rate`, `factors` and `mappings` sheets.
`recalibrate=False` deliberately preserves the rates just reviewed. It does
not select the GBM, refit the GLM or make its portfolio O/P equal to one.
For explicit training-only recalibration, see [tariff operations](../guide/operations.md).
No commercial loadings, taxes, inflation or claims-development adjustments are
implied by these synthetic technical rates.

## Continue with configuration

The [configuration guide](../guide/experiment-configuration.md) uses the saved
`portfolio.parquet` and also works with 0.5.0. Its fit commands train new models;
they do not retrieve the fitted objects retained in `models` above.

!!! note "Checkout-only in-memory workflow"

    The current checkout additionally supports `run_experiment(config, df=portfolio)`
    and `tune_experiment(config, df=portfolio)`. These arguments are absent from
    0.5.0. Use the file-based configuration guide with that release, or follow
    [checkout installation](installation.md#work-from-a-checkout) for these APIs.

[Configure an experiment](../guide/experiment-configuration.md){ .md-button .md-button--primary }
[Build diagnostic views](../guide/diagnostics-visualization.md){ .md-button }
[Continue to freMTPL2](../guide/fremtpl2.md){ .md-button }
