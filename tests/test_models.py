"""Tests for riskforge.models: RiskGLM, RiskGBM, FrequencySeverityModel.

Covers sklearn estimator conformance (`parametrize_with_checks`), the exposure
as a sample-weight contract (special cols travel inside X), the severity
filter living inside FrequencySeverityModel.fit, and the M3 acceptance test:
freq x sev approximates a direct Tweedie GLM within tolerance on synthetic data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.utils.estimator_checks import parametrize_with_checks

from riskforge.models import FrequencySeverityModel, RiskGBM, RiskGLM
from tests.conftest import make_synthetic_portfolio


@parametrize_with_checks([RiskGLM(), RiskGBM()])
def test_sklearn_compatible(estimator, check):
    check(estimator)


def _df(seed: int = 42, n: int = 20000) -> pd.DataFrame:
    df = make_synthetic_portfolio(n=n, seed=seed)
    return df


def _features(df: pd.DataFrame) -> pd.DataFrame:
    """X for a *direct* RiskGLM/RiskGBM fit: features + exposure_col, no target
    leaks (claim_count / claim_amount are dropped -- RiskGLM only strips
    ``exposure_col`` and would otherwise treat them as features)."""
    return df.drop(columns=["claim_count", "claim_amount"])


# ---------------------------------------------------------------------------
# RiskGLM
# ---------------------------------------------------------------------------


def test_riskglm_pure_premium_fit_predict_score() -> None:
    df = _df()
    X = _features(df)
    y = (df["claim_amount"] / df["exposure"]).to_numpy()
    glm = RiskGLM(family="tweedie", link="log", exposure_col="exposure").fit(X, y)
    pred = glm.predict(X)
    assert pred.shape == (len(df),)
    assert np.all(np.isfinite(pred))
    assert np.all(pred >= 0)
    s = glm.score(X, y)
    assert np.isfinite(s)
    assert glm.backend_ is not None
    assert glm.coef_ is not None
    assert glm.intercept_ is not None
    assert glm.n_features_in_ == X.shape[1]
    # backend never sees exposure_col (popped as sample_weight).
    if hasattr(glm.backend_, "feature_names_in_"):
        assert "exposure" not in glm.backend_.feature_names_in_


def test_riskglm_poisson_frequency_uses_exposure_weight() -> None:
    df = _df()
    X = _features(df)
    glm = RiskGLM(family="poisson", link="log", exposure_col="exposure")
    glm.fit(X, (df["claim_count"] / df["exposure"]).to_numpy())
    pred = glm.predict(X)
    assert np.all(pred >= 0)
    # Predicted total claim count roughly matches observed when exposure is a weight.
    obs_total = df["claim_count"].sum()
    pred_total = (pred * df["exposure"]).sum()
    assert 0.5 * obs_total <= pred_total <= 2.0 * obs_total


def test_riskglm_tweedie_power_is_used() -> None:
    df = _df()
    X = _features(df)
    y = (df["claim_amount"] / df["exposure"]).to_numpy()
    glm = RiskGLM(family="tweedie", link="log", exposure_col="exposure", tweedie_power=1.3)
    glm.fit(X, y)
    assert glm.backend_.family.power == 1.3


def test_riskglm_score_routes_sample_weight() -> None:
    df = _df()
    X = _features(df)
    y = (df["claim_amount"] / df["exposure"]).to_numpy()
    glm = RiskGLM(family="tweedie", link="log", exposure_col="exposure").fit(X, y)
    score_via_default = glm.score(X, y)
    score_via_explicit = glm.score(X, y, sample_weight=df["exposure"].to_numpy())
    assert score_via_default == pytest.approx(score_via_explicit)


# ---------------------------------------------------------------------------
# RiskGBM
# ---------------------------------------------------------------------------


def test_riskgbm_tweedie_fit_predict_score() -> None:
    df = _df().head(4000)  # ponytail: small head; the synthetic portfolio is random
    X = _features(df)
    y = (df["claim_amount"] / df["exposure"]).to_numpy()
    gbm = RiskGBM(
        objective="tweedie",
        exposure_col="exposure",
        n_estimators=50,
        num_leaves=15,
        learning_rate=0.05,
        random_state=42,
    ).fit(X, y)
    pred = gbm.predict(X)
    assert pred.shape == (len(df),)
    assert np.all(pred >= 0)
    s = gbm.score(X, y)
    assert np.isfinite(s)


def test_riskgbm_tweedie_variance_power_validated_in_init() -> None:
    with pytest.raises(ValueError, match="tweedie_variance_power"):
        RiskGBM(objective="tweedie", tweedie_variance_power=0.5)
    with pytest.raises(ValueError, match="tweedie_variance_power"):
        RiskGBM(objective="tweedie", tweedie_variance_power=2.0)
    # Powered within valid range doesn't raise.
    RiskGBM(objective="tweedie", tweedie_variance_power=1.0)
    RiskGBM(objective="tweedie", tweedie_variance_power=1.99)


def test_riskgbm_invalid_power_at_fit_after_set_params() -> None:
    gbm = RiskGBM(objective="tweedie")
    gbm.set_params(tweedie_variance_power=2.5)
    with pytest.raises(ValueError, match="tweedie_variance_power"):
        gbm.fit(np.arange(20).reshape(-1, 1), np.arange(20, dtype=float))


def test_riskgbm_monotone_constraints_dict_increasing() -> None:
    df = _df().head(2000)
    X = _features(df)
    y = (df["claim_amount"] / df["exposure"]).to_numpy()
    gbm = RiskGBM(
        objective="tweedie",
        exposure_col="exposure",
        monotone_constraints={"driver_age": 1, "vehicle_age": 1},
        n_estimators=20,
        num_leaves=15,
        learning_rate=0.1,
        random_state=42,
    ).fit(X, y)
    pred = gbm.predict(X)
    assert pred.shape == (len(df),)
    assert np.all(np.isfinite(pred))
    assert np.all(pred >= 0)


def test_riskgbm_monotone_constraints_list_passes_through() -> None:
    df = _df().head(1500)
    X = _features(df)
    mc = [1, 1, 0, 0]  # driver_age, vehicle_age, region, vehicle_brand
    gbm = RiskGBM(
        objective="tweedie",
        exposure_col="exposure",
        monotone_constraints=mc,
        n_estimators=10,
        num_leaves=8,
        learning_rate=0.1,
        random_state=42,
    ).fit(X, (df["claim_amount"] / df["exposure"]).to_numpy())
    pred = gbm.predict(X)
    assert pred.shape == (len(df),)
    assert np.all(np.isfinite(pred))


def test_riskgbm_monotone_constraints_none_default_unchanged() -> None:
    df = _df().head(1000)
    X = _features(df)
    y = (df["claim_amount"] / df["exposure"]).to_numpy()
    gbm_a = RiskGBM(
        objective="tweedie", exposure_col="exposure", n_estimators=10, random_state=42
    ).fit(X, y)
    gbm_b = RiskGBM(
        objective="tweedie",
        exposure_col="exposure",
        monotone_constraints=None,
        n_estimators=10,
        random_state=42,
    ).fit(X, y)
    np.testing.assert_allclose(gbm_a.predict(X), gbm_b.predict(X))


def test_riskgbm_monotone_constraints_invalid_dict_value_in_init() -> None:
    with pytest.raises(ValueError, match="monotone_constraints"):
        RiskGBM(objective="tweedie", monotone_constraints={"x": 2})


def test_riskgbm_monotone_constraints_unknown_col_raises_at_fit() -> None:
    df = _df().head(1000)
    X = _features(df)
    gbm = RiskGBM(
        objective="tweedie",
        exposure_col="exposure",
        monotone_constraints={"does_not_exist": 1},
        n_estimators=5,
    )
    with pytest.raises(ValueError, match="unknown columns"):
        gbm.fit(X, (df["claim_amount"] / df["exposure"]).to_numpy())


def test_riskgbm_monotone_constraints_invalid_list_values_raise_at_fit() -> None:
    df = _df().head(1000)
    X = _features(df)
    gbm = RiskGBM(
        objective="tweedie",
        exposure_col="exposure",
        monotone_constraints=[0, 1, 2, 0, 0],  # 2 is out of {-1, 0, 1}
        n_estimators=5,
    )
    with pytest.raises(ValueError, match="monotone_constraints"):
        gbm.fit(X, (df["claim_amount"] / df["exposure"]).to_numpy())


def test_riskgbm_monotone_constraints_dict_requires_dataframe() -> None:
    gbm = RiskGBM(
        objective="tweedie",
        exposure_col=None,
        monotone_constraints={"x": 1},
        n_estimators=5,
    )
    with pytest.raises(ValueError, match="dict requires a DataFrame"):
        gbm.fit(np.arange(20).reshape(-1, 1), np.arange(20, dtype=float))


# ---------------------------------------------------------------------------
# FrequencySeverityModel
# ---------------------------------------------------------------------------


def test_freq_severity_fit_predict_basics() -> None:
    df = _df()
    fs = FrequencySeverityModel(
        freq=RiskGLM(family="poisson", link="log"),
        sev=RiskGLM(family="gamma", link="log"),
        exposure_col="exposure",
        claim_count_col="claim_count",
        claim_amount_col="claim_amount",
    ).fit(df)
    pred = fs.predict(df)
    assert pred.shape == (len(df),)
    assert np.all(np.isfinite(pred))
    assert np.all(pred >= 0)
    # Severity backend was fit on a strict subset of rows with claim_count > 0.
    assert fs.sev_positive_rows_ == int((df["claim_count"] > 0).sum())
    s = fs.score(df, df["claim_amount"].to_numpy())
    assert np.isfinite(s)


def test_freq_severity_severity_fit_is_filtered() -> None:
    class _Spy:
        def __init__(self):
            self.fit_n_rows = None
            self.predict_buf = None

        def fit(self, X, y, sample_weight=None):
            self.fit_n_rows = len(np.asarray(y))
            self.predict_buf = float(np.asarray(X).shape[0])
            return self

        def predict(self, X):
            return np.ones(np.asarray(X).shape[0])

        def get_params(self, deep=True):
            return {}

        def set_params(self, **params):
            return self

    df = _df()
    fs = FrequencySeverityModel(
        freq=_Spy(),
        sev=_Spy(),
        exposure_col="exposure",
        claim_count_col="claim_count",
        claim_amount_col="claim_amount",
    ).fit(df)
    expected_pos_rows = int((df["claim_count"] > 0).sum())
    # The severity backend (a clone of the spy) was fit on claim_count > 0 rows.
    assert fs.sev_.fit_n_rows == expected_pos_rows
    # Predict returns freq(=1) * sev(=1) = pure premium per exposure unit all ones.
    assert np.allclose(fs.predict(df), 1.0)


def test_freq_severity_preserves_full_categorical_vocabulary_for_severity() -> None:
    categories = ["A", "B", "zero_only", "Other"]
    df = pd.DataFrame(
        {
            "segment": pd.Categorical(
                ["A", "A", "B", "B", "zero_only", "zero_only"],
                categories=categories,
            ),
            "exposure": [1.0, 1.5, 1.0, 2.0, 1.0, 1.0],
            "claim_count": [1, 2, 1, 3, 0, 0],
            "claim_amount": [100.0, 240.0, 150.0, 420.0, 0.0, 0.0],
        }
    )
    model = FrequencySeverityModel(
        freq=RiskGLM(family="poisson", link="log"),
        sev=RiskGLM(family="gamma", link="log"),
    )

    with pytest.warns(UserWarning) as caught:
        model.fit(df)

    assert len(caught) == 1
    message = str(caught[0].message)
    assert "segment" in message
    assert "zero_only" in message
    assert "Other" not in message
    assert list(model.sev_.backend_.categorical_levels_["segment"]) == categories
    assert np.all(np.isfinite(model.predict(df)))


def test_freq_severity_missing_special_col_raises() -> None:
    df = _df().drop(columns=["claim_count"])
    fs = FrequencySeverityModel(
        freq=RiskGLM(family="poisson", link="log"),
        sev=RiskGLM(family="gamma", link="log"),
    )
    with pytest.raises(ValueError, match="missing special columns"):
        fs.fit(df)


def test_freq_severity_requires_subestimators() -> None:
    df = _df()
    with pytest.raises(ValueError, match="`freq` and `sev`"):
        FrequencySeverityModel().fit(df)
    with pytest.raises(ValueError, match="`freq` and `sev`"):
        FrequencySeverityModel(freq=RiskGLM(family="poisson", link="log")).fit(df)


# ---------------------------------------------------------------------------


def test_riskgbm_monotone_sequence_requires_exact_post_exposure_shape() -> None:
    df = _df().head(500)
    X = _features(df)
    y = (df["claim_amount"] / df["exposure"]).to_numpy()
    with pytest.raises(ValueError, match="post-exposure"):
        RiskGBM(exposure_col="exposure", monotone_constraints=[0] * 5).fit(X, y)
    with pytest.raises(ValueError, match="one-dimensional"):
        RiskGBM(
            exposure_col="exposure",
            monotone_constraints=[[0, 0], [0, 0]],
        ).fit(X, y)


def test_riskgbm_rejects_monotone_constraint_on_categorical_column() -> None:
    df = _df().head(500)
    X = _features(df)
    y = (df["claim_amount"] / df["exposure"]).to_numpy()
    with pytest.raises(ValueError, match="categorical"):
        RiskGBM(
            exposure_col="exposure",
            monotone_constraints={"region": 1},
        ).fit(X, y)


def test_freq_severity_rejects_portfolio_without_severity_observations() -> None:
    df = _df(n=100).assign(claim_count=0, claim_amount=0.0)
    model = FrequencySeverityModel(
        freq=RiskGLM(family="poisson", link="log"),
        sev=RiskGLM(family="gamma", link="log"),
    )
    with pytest.raises(ValueError, match="severity observation"):
        model.fit(df)


def test_freq_severity_score_compares_rates_with_exposure_weights() -> None:
    from sklearn.metrics import d2_tweedie_score

    df = _df(n=2000)
    model = FrequencySeverityModel(
        freq=RiskGLM(family="poisson", link="log"),
        sev=RiskGLM(family="gamma", link="log"),
    ).fit(df)
    observed_amount = df["claim_amount"].to_numpy()
    expected = d2_tweedie_score(
        observed_amount / df["exposure"].to_numpy(),
        model.predict(df),
        power=1.5,
        sample_weight=df["exposure"].to_numpy(),
    )
    assert model.score(df, observed_amount) == pytest.approx(expected)


def test_m3_acceptance_freq_sev_approximates_direct_tweedie() -> None:
    from riskforge.metrics import gini, op_ratio

    df = _df()
    X = _features(df)
    direct = RiskGLM(
        family="tweedie",
        link="log",
        exposure_col="exposure",
        tweedie_power=1.5,
    ).fit(X, (df["claim_amount"] / df["exposure"]).to_numpy())
    freq_sev = FrequencySeverityModel(
        freq=RiskGLM(family="poisson", link="log", alpha=0.001),
        sev=RiskGLM(family="gamma", link="log", alpha=0.001),
    ).fit(df)

    observed = df["claim_amount"].to_numpy()
    exposure = df["exposure"].to_numpy()
    direct_pred = direct.predict(X)
    freq_sev_pred = freq_sev.predict(df)
    direct_gini = gini(observed, direct_pred, exposure)
    freq_sev_gini = gini(observed, freq_sev_pred, exposure)
    assert freq_sev_gini > 0.05
    assert abs(freq_sev_gini - direct_gini) < 0.25
    assert 0.85 <= op_ratio(observed, direct_pred, exposure) <= 1.15
    assert 0.85 <= op_ratio(observed, freq_sev_pred, exposure) <= 1.15
