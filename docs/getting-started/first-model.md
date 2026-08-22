# First model

This example creates its own portfolio, holds out the latest underwriting
periods, fits a Tweedie generalized linear model (GLM), and writes one
calibration chart. It needs only the core Azoic installation and no network
access.

!!! warning "The exposure convention"

    The response is `claim_amount / exposure` and exposure is the sample
    weight carried inside `X`. Do not also use `log(exposure)` as an offset;
    that would mix the rate and aggregate formulations.

## Run the complete example

Save the following as `first_model.py` in an empty directory and run
`python first_model.py`.

```python
from pathlib import Path

import numpy as np
import pandas as pd

from azoic.metrics import calibration_table, gini, op_ratio
from azoic.models import RiskGLM
from azoic.plots import plot_calibration
from azoic.validation import temporal_split

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

train_idx, test_idx = temporal_split(portfolio, "period", test_size=0.2)
features = ["driver_age", "vehicle_age", "region", "exposure"]
train = portfolio.iloc[train_idx]
test = portfolio.iloc[test_idx]

model = RiskGLM(
    family="tweedie",
    link="log",
    exposure_col="exposure",
    tweedie_power=1.5,
    random_state=42,
)
model.fit(
    train[features],
    train["claim_amount"].to_numpy() / train["exposure"].to_numpy(),
)

prediction = model.predict(test[features])
actual_claim_amount = test["claim_amount"].to_numpy()
test_exposure = test["exposure"].to_numpy()

test_gini = gini(actual_claim_amount, prediction, test_exposure)
test_op = op_ratio(actual_claim_amount, prediction, test_exposure)
calibration = calibration_table(
    actual_claim_amount,
    prediction,
    test_exposure,
    n_bins=10,
)

chart_path = Path("first-model-calibration.png")
plot_calibration(calibration, path=chart_path)

print(f"train rows: {len(train):,}; test rows: {len(test):,}")
print(f"period boundary: {train['period'].max()} < {test['period'].min()}")
print(f"test Gini: {test_gini:.3f}")
print(f"test O/P ratio: {test_op:.3f}")
print(calibration.round(3).to_string(index=False))
print(f"wrote {chart_path.resolve()}")
```

!!! warning "Why the split is leakage-safe"

    `temporal_split` trains on earlier periods and tests on later ones. If the
    requested boundary falls inside a period, every row with that equal
    timestamp stays on the same side. Missing time values are rejected.

## Read the result

Gini answers whether the model ranks policies from lower to higher risk; it
does not measure pricing level. A positive held-out Gini is useful ranking
signal. The O/P ratio compares observed with predicted aggregate claim amount;
1.0 is the portfolio-level target.

The calibration table and chart then reveal whether a satisfactory portfolio
total hides over-pricing or under-pricing inside risk deciles. Point size
represents exposure, and distance from the diagonal represents segment-level
miscalibration. Sparse segments deserve less confidence than exposure-heavy
ones.

This synthetic portfolio is deliberately small and clean. Real work still
needs data validation, business review, an inner model-selection split, and
one untouched final test evaluation.

[Configure an experiment](../guide/experiment-configuration.md){ .md-button .md-button--primary }
[Build diagnostic views](../guide/diagnostics-visualization.md){ .md-button }
[Continue to freMTPL2](../guide/fremtpl2.md){ .md-button }
