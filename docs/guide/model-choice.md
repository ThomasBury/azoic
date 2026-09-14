# Model choice and fitting

Start with the model whose constraints match the decision, then ask whether a
more flexible candidate improves held-out evidence enough to justify itself.

All Azoic estimators take pure-premium rate targets in `fit` and `score`
and return pure-premium rates from `predict`.

| Candidate | Use it when | Main trade-off |
|---|---|---|
| `RiskGLM` | Stable multiplicative relativities, direct coefficient review, and tariff export matter | Additive linear predictor needs explicit feature engineering or binning |
| `RiskGBM` | Nonlinearities and interactions materially improve held-out diagnostics | Harder to explain; export requires GBM-to-GLM distillation |
| `FrequencySeverityModel` | Frequency and claim size need separate families or interpretation | Two submodels create more ways to miscalibrate the product |

## Fit a direct pure-premium model

Special columns travel inside `X`. `RiskGLM` removes the exposure column and
passes it to glum as `sample_weight`.

!!! note "Contrast with YAML configs"

    This direct-Python contract inverts inside an `ExperimentConfig`: YAML
    `features:` must exclude `exposure` and every other special column, which
    the workflow derives from `spec`. See
    [Experiments and CLI](experiment-configuration.md).

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

## Inspect feature effects with PDP and ICE

Partial dependence (PDP) averages predictions while varying one feature.
Individual conditional expectation (ICE) keeps one curve per sampled row, so it
can reveal effects hidden by the average. Pass a fitted Azoic estimator directly;
a fitted pipeline returned by `run_experiment(..., return_estimators=True)` works
the same way.

```python
from sklearn.inspection import PartialDependenceDisplay

explanation_features = ["driver_age", "vehicle_age"]
X_explain = X_train.copy()
X_explain[explanation_features] = X_explain[explanation_features].astype(float)

fitted_estimator = gbm  # A workflow-returned pipeline can be used here instead.
display = PartialDependenceDisplay.from_estimator(
    fitted_estimator,
    X_explain,
    features=explanation_features,
    kind="both",
    method="brute",
    sample_weight=X_explain["exposure"],
    subsample=200,
    random_state=42,
    ice_lines_kw={"alpha": 0.15},
    pd_line_kw={"linewidth": 2},
)
display.figure_.tight_layout()
```

Convert explained integer columns to floats because scikit-learn writes the
PDP grid values into working copies of those columns.

For a pipeline, name `features` with the original input columns; fitted
preprocessing runs inside the pipeline for every grid value. The exposure
weights affect the PDP average. They do not alter an individual ICE curve, and
`subsample` limits only the displayed ICE rows; `random_state` makes that choice
repeatable.

## Inspect LightGBM native contributions

`RiskGBM.backend_` exposes LightGBM's native feature contributions. A workflow
pipeline must transform the original columns before the backend call. Exposure
then comes out because it weighted fitting but was not a backend feature.

```python
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

fitted_estimator = gbm  # Or a fitted workflow pipeline ending in RiskGBM.
if isinstance(fitted_estimator, Pipeline):
    model = fitted_estimator[-1]
    X_backend = fitted_estimator[:-1].transform(X_explain)
else:
    model = fitted_estimator
    X_backend = X_explain

X_backend = X_backend.drop(columns=model.exposure_col).copy()
categorical_columns = X_backend.select_dtypes(include=["object", "string"]).columns
X_backend[categorical_columns] = X_backend[categorical_columns].astype("category")

values = model.backend_.predict(X_backend, pred_contrib=True)
contributions = pd.DataFrame(
    values,
    columns=[*model.backend_.feature_name_, "expected_value"],
    index=X_explain.index,
)

raw_score = model.backend_.predict(X_backend, raw_score=True)
np.testing.assert_allclose(contributions.sum(axis=1), raw_score)
np.testing.assert_allclose(
    np.exp(raw_score),
    fitted_estimator.predict(X_explain),
)
contributions.head()
```

The final `expected_value` column is the backend's expected output. Adding it to
the feature contributions reproduces the raw LightGBM score. For this Tweedie
model the raw score is on the log scale, so exponentiating it reproduces the
public pure-premium prediction.

The example casts both `object` and `string` dtypes explicitly for a reason:
the estimator's fit-time auto-cast converts only `object` columns to
categorical, so pandas `string` dtype columns pass through unchanged unless you
cast them yourself.

!!! warning "Interpretation boundaries"

    - Correlated features can make PDP evaluate implausible feature combinations.
    - ICE shows heterogeneity in the fitted model, not prediction uncertainty.
    - Native contributions are model-specific associations on the raw score
      scale. They are not causal effects or additive premium amounts.
    - These views do not replace held-out Gini, calibration, O/P, and stability
      checks.

## Fit frequency times severity

The meta-estimator owns the actuarial split: frequency uses every row, while
severity uses only `claim_count > 0` and weights by claim count. Before
deriving rates or fitting either component, it rejects non-positive or non-finite
exposure, negative or non-finite counts and amounts, and rows where count and
amount are not zero or positive together. This validation also applies when
`y` is omitted, so a recorded loss with zero claims cannot be silently excluded.

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
frequency_severity.fit(train[columns], y_train)
prediction = frequency_severity.predict(test[columns])
score = frequency_severity.score(
    test[columns],
    test["claim_amount"] / test["exposure"],
)
```

Do not filter severity rows in user code; doing so can desynchronize the two
submodels and breaks the estimator's pipeline contract. The rate target may be
omitted from `fit` because the outcomes already travel inside `X`; when
supplied, it is checked against `claim_amount / exposure`.

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
