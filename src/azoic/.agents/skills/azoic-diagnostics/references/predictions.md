# Ranking and calibration from existing predictions

Check the installed version first. Supply `predictions.parquet` with aligned
aggregate `claim_amount`, exposure in years and existing pure-premium `rate`.
Verify the population and row alignment; rates must refer to the same period and
currency basis. This block never fits or recalibrates a model.

```python
import numpy as np
import pandas as pd
from azoic import calibration_table, gini, op_ratio
from sklearn.metrics import mean_tweedie_deviance

predictions = pd.read_parquet("predictions.parquet")
amount = predictions.claim_amount.to_numpy()
exposure = predictions.exposure.to_numpy()
rate = predictions.rate.to_numpy()
diagnostics = pd.DataFrame([
    {"scale": scale,
     "gini": gini(amount, rate * scale, exposure),
     "o_p_ratio": op_ratio(amount, rate * scale, exposure),
     "deviance": mean_tweedie_deviance(amount / exposure, rate * scale,
                                      sample_weight=exposure, power=1.5)}
    for scale in (1.0, 2.0)
]).set_index("scale")
calibration = calibration_table(amount, rate, exposure)
np.testing.assert_allclose(diagnostics.loc[2.0, "gini"], diagnostics.loc[1.0, "gini"])
np.testing.assert_allclose(diagnostics.loc[2.0, "o_p_ratio"],
                           diagnostics.loc[1.0, "o_p_ratio"] / 2)
print(diagnostics)
```

The doubled prediction is a labelled diagnostic counterfactual, not a candidate
revision. It preserves ranking while worsening or improving level depending on
the original O/P. O/P above 1 means aggregate predicted cost is below observed
claims, not automatically that future prices should rise by that ratio. Pair
the portfolio level with segment calibration, volume, claim maturity and target
basis. Gini alone cannot identify the better calibrated model. Deviance above
uses observed rates and fixed power 1.5; Azoic tables use aggregate claims.

For zero/nonpositive predictions, assess their domain before requesting a
Tweedie deviance; do not hide invalid predictions by clipping them. Explain any
undefined diagnostic. Teacher/student agreement is fidelity, and needs a separate
comparison with observed claims before making performance claims.
