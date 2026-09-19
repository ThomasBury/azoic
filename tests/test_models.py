"""Tests for azoic.models: RiskGLM, RiskGBM, FrequencySeverityModel.

Covers sklearn estimator conformance (`parametrize_with_checks`), the exposure
as a sample-weight contract (special cols travel inside X), the severity
filter living inside FrequencySeverityModel.fit, and the M3 acceptance test:
freq x sev approximates a direct Tweedie GLM within tolerance on synthetic data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.metrics import d2_tweedie_score
from sklearn.utils.estimator_checks import parametrize_with_checks

from azoic.models import FrequencySeverityModel, RiskGBM, RiskGLM
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
    y_rate = (df["claim_amount"] / df["exposure"]).to_numpy()
    fs = FrequencySeverityModel(
        freq=RiskGLM(family="poisson", link="log"),
        sev=RiskGLM(family="gamma", link="log"),
        exposure_col="exposure",
        claim_count_col="claim_count",
        claim_amount_col="claim_amount",
    ).fit(df, y_rate)
    pred = fs.predict(df)
    assert pred.shape == (len(df),)
    assert np.all(np.isfinite(pred))
    assert np.all(pred >= 0)
    # Severity backend was fit on a strict subset of rows with claim_count > 0.
    assert fs.sev_positive_rows_ == int((df["claim_count"] > 0).sum())
    s = fs.score(df, y_rate)
    assert np.isfinite(s)


@pytest.mark.parametrize(
    ("path", "supply_rate"),
    [
        ("direct", False),
        ("direct", True),
        ("pipeline", False),
        ("pipeline", True),
        ("workflow", True),
    ],
)
@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("claim_amount", 1000.0, "zero or positive together"),
        ("claim_count", 1.0, "zero or positive together"),
        ("exposure", 0.0, "positive finite"),
        ("exposure", -1.0, "positive finite"),
        ("exposure", np.nan, "positive finite"),
        ("exposure", np.inf, "positive finite"),
        ("exposure", -np.inf, "positive finite"),
        ("claim_count", -1.0, "non-negative finite"),
        ("claim_count", np.nan, "non-negative finite"),
        ("claim_count", np.inf, "non-negative finite"),
        ("claim_count", -np.inf, "non-negative finite"),
        ("claim_amount", -1.0, "non-negative finite"),
        ("claim_amount", np.nan, "non-negative finite"),
        ("claim_amount", np.inf, "non-negative finite"),
        ("claim_amount", -np.inf, "non-negative finite"),
    ],
)
def test_freq_severity_rejects_invalid_outcomes_before_components(
    tmp_path, monkeypatch, path, supply_rate, column, value, message
) -> None:
    from unittest.mock import Mock

    from sklearn.pipeline import Pipeline

    from azoic.workflow import ExperimentConfig, ModelSpec, run_experiment

    df = pd.DataFrame(
        {
            "risk": [0.0, 1.0, 2.0, 3.0],
            "exposure": [0.5, 1.0, 0.25, 1.0],
            "claim_count": [0.0, 1.0, 2.0, 0.0],
            "claim_amount": [0.0, 30.0, 40.0, 0.0],
        }
    )
    df.loc[0, column] = value
    model_spec = ModelSpec(
        kind="frequency_severity",
        frequency=ModelSpec(params={"family": "poisson", "link": "log"}),
        severity=ModelSpec(params={"family": "gamma", "link": "log"}),
    )
    config = ExperimentConfig(
        data_path=str(tmp_path / "invalid.parquet"),
        spec={"target": "claim_amount", "exposure": "exposure", "claim_count": "claim_count"},
        models={"freq-sev": model_spec},
    )
    model = model_spec.build(config.spec)
    estimator = Pipeline([("model", model)]) if path == "pipeline" else model
    with np.errstate(divide="ignore", invalid="ignore"):
        rate = (df["claim_amount"] / df["exposure"]).to_numpy() if supply_rate else None
    clone = Mock(side_effect=AssertionError("components must not be cloned for invalid outcomes"))
    fit = Mock(side_effect=AssertionError("components must not fit invalid outcomes"))
    monkeypatch.setattr("azoic.models.clone", clone)
    monkeypatch.setattr(RiskGLM, "fit", fit)
    df.to_parquet(config.data_path)

    with pytest.raises(ValueError, match=message), np.errstate(divide="raise", invalid="raise"):
        if path == "workflow":
            run_experiment(config)
        else:
            estimator.fit(df, rate)

    clone.assert_not_called()
    fit.assert_not_called()
    assert not hasattr(model, "freq_")
    assert not hasattr(model, "sev_")


def test_freq_severity_fit_rejects_aggregate_or_mismatched_target() -> None:
    df = _df(n=200)
    rate = (df["claim_amount"] / df["exposure"]).to_numpy()
    model = FrequencySeverityModel(
        freq=RiskGLM(family="poisson", link="log"),
        sev=RiskGLM(family="gamma", link="log"),
    )
    for invalid in (df["claim_amount"].to_numpy(), rate + 1.0):
        with pytest.raises(ValueError, match="claim_amount / exposure"):
            model.fit(df, invalid)


def test_freq_severity_fit_rejects_nonfinite_target() -> None:
    df = _df(n=200)
    rate = (df["claim_amount"] / df["exposure"]).to_numpy()
    rate[0] = np.inf
    model = FrequencySeverityModel(
        freq=RiskGLM(family="poisson", link="log"),
        sev=RiskGLM(family="gamma", link="log"),
    )
    with pytest.raises(ValueError, match="finite"):
        model.fit(df, rate)


def test_freq_severity_fit_rejects_wrong_target_shape() -> None:
    df = _df(n=200)
    rate = (df["claim_amount"] / df["exposure"]).to_numpy()
    model = FrequencySeverityModel(
        freq=RiskGLM(family="poisson", link="log"),
        sev=RiskGLM(family="gamma", link="log"),
    )
    for invalid in (rate[:, None], rate[:-1]):
        with pytest.raises(ValueError, match="one-dimensional"):
            model.fit(df, invalid)


def test_freq_severity_severity_fit_is_filtered() -> None:
    class _Spy:
        def __init__(self):
            self.fit_n_rows = None
            self.predict_buf = None

        def fit(self, X, y, sample_weight=None):
            self.fit_n_rows = len(np.asarray(y))
            self.predict_buf = float(np.asarray(X).shape[0])
            self.fit_X = X.copy()
            self.fit_y = np.asarray(y).copy()
            self.fit_weight = np.asarray(sample_weight).copy()
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
    positive = df["claim_count"] > 0
    features = df.drop(columns=["exposure", "claim_count", "claim_amount"]).astype(
        {"region": "category", "vehicle_brand": "category"}
    )
    pd.testing.assert_frame_equal(fs.freq_.fit_X, features)
    pd.testing.assert_frame_equal(fs.sev_.fit_X, features.loc[positive])
    np.testing.assert_allclose(fs.freq_.fit_y, df["claim_count"] / df["exposure"])
    np.testing.assert_array_equal(fs.freq_.fit_weight, df["exposure"])
    np.testing.assert_allclose(
        fs.sev_.fit_y, df.loc[positive, "claim_amount"] / df.loc[positive, "claim_count"]
    )
    np.testing.assert_array_equal(fs.sev_.fit_weight, df.loc[positive, "claim_count"])
    np.testing.assert_array_equal(fs.predict(features), fs.predict(df))
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
    observed_rate = (df["claim_amount"] / df["exposure"]).to_numpy()
    expected = d2_tweedie_score(
        observed_rate,
        model.predict(df),
        power=1.5,
        sample_weight=df["exposure"].to_numpy(),
    )
    assert model.score(df, observed_rate) == pytest.approx(expected)

    explicit_weight = np.linspace(1.0, 2.0, len(df))
    expected_explicit = d2_tweedie_score(
        observed_rate,
        model.predict(df),
        power=1.5,
        sample_weight=explicit_weight,
    )
    assert model.score(df, observed_rate, sample_weight=explicit_weight) == pytest.approx(
        expected_explicit
    )


def test_m3_acceptance_freq_sev_approximates_direct_tweedie() -> None:
    from azoic.metrics import gini, op_ratio

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


@pytest.mark.parametrize(("family", "power"), [("poisson", 1), ("tweedie", 1.5), ("gamma", 2)])
@pytest.mark.parametrize("varying_feature", [False, True])
def test_log_glm_mean_target_and_intercept_balance(family, power, varying_feature) -> None:
    rate = np.array([1.0, 3.0, 2.0, 8.0, 4.0])
    exposure = np.array([1.0, 2.0, 1.0, 3.0, 2.0])
    X = pd.DataFrame(
        {"x": np.arange(-2.0, 3.0) if varying_feature else np.zeros(5), "exposure": exposure}
    )
    model = RiskGLM(
        family=family,
        tweedie_power=power,
        link="log",
        alpha=0,
        exposure_col="exposure",
        gradient_tol=1e-9,
    ).fit(X, rate)
    prediction = model.predict(X)
    score = np.average((prediction - rate) * prediction ** (1 - power), weights=exposure)
    assert abs(score) < 1e-8
    ratio = np.dot(exposure, rate) / np.dot(exposure, prediction)
    if not varying_feature:
        np.testing.assert_allclose(prediction, np.average(rate, weights=exposure), rtol=1e-8)
    if not varying_feature or power == 1:
        assert ratio == pytest.approx(1, abs=1e-8)
    else:
        assert abs(ratio - 1) > 1e-3


# ---------------------------------------------------------------------------
# Configured exposure column is fail-closed (M31)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "estimator",
    [
        RiskGLM(family="poisson", exposure_col="exposure"),
        RiskGBM(objective="tweedie", exposure_col="exposure", n_estimators=10),
    ],
    ids=["glm", "gbm"],
)
def test_fit_score_raise_when_configured_exposure_col_missing(estimator) -> None:
    """A configured exposure_col absent from X must not silently fit unweighted
    (the exposure-weight pure-premium convention). predict stays permissive:
    new data need not carry the exposure column."""
    df = _df()
    X = _features(df)
    y = (df["claim_amount"] / df["exposure"]).to_numpy()
    X_missing = X.drop(columns=["exposure"])
    with pytest.raises(ValueError, match="exposure_col 'exposure' not found in X"):
        estimator.fit(X_missing, y)
    estimator.fit(X, y)
    with pytest.raises(ValueError, match="exposure_col 'exposure' not found in X"):
        estimator.score(X_missing, y)
    pred = estimator.predict(X_missing)
    assert np.isfinite(pred).all()


def test_exposure_col_with_ndarray_raises_at_fit() -> None:
    glm = RiskGLM(exposure_col="exposure")
    with pytest.raises(ValueError, match="not found in X"):
        glm.fit(np.zeros((5, 2)), np.ones(5))


def test_freq_sev_subestimator_with_exposure_col_uses_explicit_weights() -> None:
    """FrequencySeverityModel strips the special columns and passes explicit
    component weights, so a sub-estimator configured with exposure_col must
    still fit weighted: its coefficients must equal a plain weighted fit."""
    df = _df()
    X = _features(df).drop(columns=["exposure"])
    exposure = df["exposure"].to_numpy()
    cc = df["claim_count"].to_numpy()
    model = FrequencySeverityModel(
        freq=RiskGLM(family="poisson", exposure_col="exposure"),
        sev=RiskGLM(family="gamma", exposure_col="exposure"),
    ).fit(df)
    freq_ref = RiskGLM(family="poisson").fit(X, cc / exposure, sample_weight=exposure)
    pos = cc > 0
    sev_ref = RiskGLM(family="gamma").fit(
        X.loc[pos],
        df["claim_amount"].to_numpy()[pos] / cc[pos],
        sample_weight=cc[pos],
    )
    np.testing.assert_allclose(model.freq_.coef_, freq_ref.coef_)
    np.testing.assert_allclose(model.sev_.coef_, sev_ref.coef_)


@pytest.mark.parametrize(
    "estimator",
    [
        RiskGLM(family="poisson", exposure_col="exposure"),
        RiskGBM(objective="tweedie", exposure_col="exposure", n_estimators=10),
    ],
    ids=["glm", "gbm"],
)
def test_explicit_sample_weight_overrides_missing_exposure_col(estimator) -> None:
    """An explicit sample_weight is a first-class override: a configured
    exposure_col absent from X must not raise when weights are supplied, and
    the result must equal an unconfigured estimator on the same weights."""
    df = _df()
    X = _features(df).drop(columns=["exposure"])
    y = (df["claim_amount"] / df["exposure"]).to_numpy()
    w = df["exposure"].to_numpy()
    estimator.fit(X, y, sample_weight=w)
    ref = estimator.__class__(**{**estimator.get_params(), "exposure_col": None}).fit(
        X, y, sample_weight=w
    )
    np.testing.assert_allclose(estimator.predict(X), ref.predict(X))


@pytest.mark.parametrize(
    "estimator",
    [
        RiskGLM(family="tweedie", exposure_col="exposure"),
        RiskGBM(objective="tweedie", exposure_col="exposure", n_estimators=10),
    ],
    ids=["glm", "gbm"],
)
@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf, -1.0])
def test_fit_score_reject_invalid_sample_weight(estimator, bad) -> None:
    """LightGBM silently accepts negative/NaN weights; glum does not. Both
    backends must fail closed through the shared weight pop (popped exposure
    column or explicit sample_weight alike)."""
    df = _df(n=2000)
    X = _features(df)
    X.loc[df.index[0], "exposure"] = bad
    y = (df["claim_amount"] / df["exposure"]).to_numpy()
    match = "finite" if not np.isfinite(bad) else "non-negative"
    with pytest.raises(ValueError, match=match):
        estimator.fit(X, y)
    clean = RiskGLM(family="tweedie") if isinstance(estimator, RiskGLM) else RiskGBM(
        objective="tweedie", n_estimators=10
    )
    w = df["exposure"].to_numpy()
    w[0] = bad
    with pytest.raises(ValueError, match=match):
        clean.fit(_features(df).drop(columns=["exposure"]), y, sample_weight=w)


# ---------------------------------------------------------------------------
# One-day exposure floor (M33)
# ---------------------------------------------------------------------------


def test_popped_exposure_below_one_day_raises() -> None:
    """The exposure floor lives on the popped column path (fit/score); the
    tolerance keeps freMTPL2's ulp-low one-day fractions legal."""
    df = _df(n=2000)
    X = _features(df)
    y = (df["claim_amount"] / df["exposure"]).to_numpy()
    X.loc[df.index[0], "exposure"] = 0.0027322404371584  # freMTPL2 one-day row
    RiskGBM(objective="tweedie", exposure_col="exposure", n_estimators=10).fit(X, y)
    X.loc[df.index[0], "exposure"] = 0.001  # ~2.9 hours: sub-day data
    with pytest.raises(ValueError, match="1/366"):
        RiskGBM(objective="tweedie", exposure_col="exposure", n_estimators=10).fit(X, y)
    with pytest.raises(ValueError, match="1/366"):
        RiskGLM(family="tweedie", exposure_col="exposure").fit(X, y)


def test_explicit_sample_weight_is_not_floored() -> None:
    """Explicit weights are not exposure (severity routes claim counts, sklearn
    checks feed arange-style weights): no one-day floor on this path."""
    df = _df(n=2000)
    X = _features(df).drop(columns=["exposure"])
    y = (df["claim_amount"] / df["exposure"]).to_numpy()
    w = df["exposure"].to_numpy()
    w[0] = 1e-6
    RiskGBM(objective="tweedie", n_estimators=10).fit(X, y, sample_weight=w)


def test_freq_severity_rejects_sub_day_exposure() -> None:
    df = _df(n=2000)
    df.loc[df.index[0], "exposure"] = 0.001
    df.loc[df.index[0], "claim_amount"] = 0.0
    df.loc[df.index[0], "claim_count"] = 0.0
    model = FrequencySeverityModel(freq=RiskGLM(family="poisson"), sev=RiskGLM(family="gamma"))
    with pytest.raises(ValueError, match="1/366"):
        model.fit(df)


# ---------------------------------------------------------------------------
# Score objective mapping + clipping warning (M32)
# ---------------------------------------------------------------------------


def test_riskgbm_score_raises_for_unmapped_objective() -> None:
    df = _df(n=2000)
    X = _features(df)
    y = (df["claim_amount"] / df["exposure"]).to_numpy()
    gbm = RiskGBM(objective="regression_l1", n_estimators=10, exposure_col="exposure")
    gbm.fit(X, y)
    with pytest.raises(ValueError, match="no Tweedie-deviance mapping.*scoring="):
        gbm.score(X, y)


@pytest.mark.parametrize(
    "objective", ["regression", "regression_l2", "rmse", "l2", "mean_squared_error", "mse"]
)
def test_riskgbm_score_l2_aliases_use_normal_deviance(objective: str) -> None:
    df = _df(n=2000)
    X = _features(df)
    y = (df["claim_amount"] / df["exposure"]).to_numpy()
    gbm = RiskGBM(objective=objective, n_estimators=10, exposure_col="exposure")
    gbm.fit(X, y)
    score = gbm.score(X, y)
    assert np.isfinite(score)
    expected = d2_tweedie_score(y, gbm.predict(X), power=0.0, sample_weight=df["exposure"])
    assert score == pytest.approx(expected)


def test_freq_sev_predict_warns_when_clipping_negative_components() -> None:
    class _ConstantRegressor(RegressorMixin, BaseEstimator):
        def __init__(self, value=-1.0):
            self.value = value

        def fit(self, X, y, sample_weight=None):
            return self

        def predict(self, X):
            return np.full(len(X), self.value)

    df = _df()
    model = FrequencySeverityModel(
        freq=_ConstantRegressor(-1.0), sev=_ConstantRegressor(2.0)
    ).fit(df)
    with pytest.warns(UserWarning, match="clipped .* negative component"):
        pred = model.predict(df)
    assert (pred == 0.0).all()  # -1 clipped to 0, x 2
