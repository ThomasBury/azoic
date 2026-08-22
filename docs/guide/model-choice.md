# Model choice and fitting

Start with the model whose constraints match the decision, then ask whether a
more flexible candidate improves held-out evidence enough to justify itself.

| Candidate | Use it when | Main trade-off |
|---|---|---|
| `RiskGLM` | Stable multiplicative relativities, direct coefficient review, and tariff export matter | Additive linear predictor needs explicit feature engineering or binning |
| `RiskGBM` | Nonlinearities and interactions materially improve held-out diagnostics | Harder to explain; export requires GBM-to-GLM distillation |
| `FrequencySeverityModel` | Frequency and claim size need separate families or interpretation | Two submodels create more ways to miscalibrate the product |

## Fit a direct pure-premium model

Special columns travel inside `X`. `RiskGLM` removes the exposure column and
passes it to glum as `sample_weight`.

```python
from azoic.models import RiskGLM

feature_columns = ["driver_age", "vehicle_age", "region", "exposure"]
X_train = train[feature_columns]
y_train = train["claim_amount"] / train["exposure"]

glm = RiskGLM(
    family="tweedie",
    link="log",
    exposure_col="exposure",
    tweedie_power=1.5,
    alpha=0.001,
    random_state=42,
)
glm.fit(X_train, y_train)
prediction = glm.predict(test[feature_columns])
```

!!! important "One exposure formulation"

    For pure premium, fit
    \(y = \text{claim amount} / \text{exposure}\) with exposure as weight.
    Use `offset=log(exposure)` only when the response is aggregate claim amount.
    Never use both.

`RiskGBM` uses the same `X` and `y` contract:

```python
from azoic.models import RiskGBM

gbm = RiskGBM(
    objective="tweedie",
    exposure_col="exposure",
    tweedie_variance_power=1.5,
    n_estimators=100,
    num_leaves=31,
    learning_rate=0.05,
    random_state=42,
)
gbm.fit(X_train, y_train)
```

Tweedie variance power must satisfy \(1.0 \le p < 2.0\). LightGBM monotonic
constraints may be a sequence in post-exposure feature order or a mapping from
numeric feature name to `-1`, `0`, or `1`. Categorical features cannot carry a
non-zero constraint.

## Fit frequency times severity

The meta-estimator owns the actuarial split: frequency uses every row, while
severity uses only `claim_count > 0` and weights by claim count.

```python
from azoic.models import FrequencySeverityModel, RiskGLM

columns = [
    "driver_age",
    "vehicle_age",
    "region",
    "exposure",
    "claim_count",
    "claim_amount",
]

frequency_severity = FrequencySeverityModel(
    freq=RiskGLM(family="poisson", link="log"),
    sev=RiskGLM(family="gamma", link="log"),
    exposure_col="exposure",
    claim_count_col="claim_count",
    claim_amount_col="claim_amount",
)
frequency_severity.fit(train[columns])
prediction = frequency_severity.predict(test[columns])
```

Do not filter severity rows in user code; doing so can desynchronize the two
submodels and breaks the estimator's pipeline contract.

## Compare candidates fairly

- Use the same outer split and features.
- Select preprocessing and hyperparameters on inner training data only.
- Compare deviance only within a common response family.
- Pair Gini with O/P and calibration; ranking alone is not adequacy.
- Evaluate the untouched outer test once.
- Prefer the simpler model unless additional complexity improves a decision,
  not merely an in-sample score.

[Configure reproducible experiments](experiment-configuration.md){ .md-button .md-button--primary }
[Interpret the diagnostics](actuarial-workflow.md){ .md-button }
