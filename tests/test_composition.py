"""Independent component units and sklearn integration; no Azoic inheritance required."""

import numpy as np
import pandas as pd
import pytest
from sklearn.base import BaseEstimator, clone
from sklearn.dummy import DummyRegressor
from sklearn.model_selection import KFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer

from azoic import FrequencySeverityModel, op_ratio


def _portfolio():
    return pd.DataFrame(
        {
            "constant": [1.0] * 3,
            "exposure": [1.0, 3.0, 2.0],
            "claim_count": [1, 2, 0],
            "claim_amount": [10.0, 60.0, 0.0],
        }
    )


def _assert_predictions(model, frame):
    prediction = model.predict(frame)
    assert prediction.shape == (len(frame),)
    assert np.isfinite(prediction).all()
    np.testing.assert_allclose(prediction, 35 / 3)
    assert np.dot(prediction, frame.exposure) == pytest.approx(70)
    assert op_ratio(frame.claim_amount, prediction, frame.exposure) == pytest.approx(1)


class RecordingMean(BaseEstimator):
    """A cloneable component without score; modes deliberately break the contract."""

    def __init__(self, mode="mean"):
        self.mode = mode

    def fit(self, X, y, sample_weight=None):
        self.frame_ = X.copy(deep=True)
        self.target_ = np.asarray(y).copy()
        self.weight_ = np.asarray(sample_weight).copy()
        if self.mode == "ignore_weights":
            self.value_ = np.mean(y)
        elif self.mode == "aggregate":
            self.value_ = np.dot(y, sample_weight)
        else:
            self.value_ = np.average(y, weights=sample_weight)
        return self

    def predict(self, X):
        shape = (len(X), 1) if self.mode == "column" else (len(X),)
        return np.full(shape, self.value_)


def test_components_receive_rates_weights_and_only_features():
    frame = _portfolio()
    frame["category"] = pd.Categorical(["a", "b", "a"], categories=["a", "b", "unused"])
    original = frame.copy(deep=True)
    freq, sev = RecordingMean(), RecordingMean()
    model = FrequencySeverityModel(freq=freq, sev=sev)
    assert model.fit(frame, frame.claim_amount / frame.exposure) is model
    np.testing.assert_allclose(model.freq_.target_, [1, 2 / 3, 0])
    np.testing.assert_allclose(model.freq_.weight_, [1, 3, 2])
    np.testing.assert_allclose(model.sev_.target_, [10, 30])
    np.testing.assert_allclose(model.sev_.weight_, [1, 2])
    pd.testing.assert_frame_equal(model.freq_.frame_, frame[["constant", "category"]])
    pd.testing.assert_frame_equal(model.sev_.frame_, frame.loc[[0, 1], ["constant", "category"]])
    assert not hasattr(freq, "value_") and not hasattr(sev, "value_")
    assert model.freq_ is not freq and model.sev_ is not sev
    _assert_predictions(model, frame)
    np.testing.assert_allclose(model.predict(frame[["constant", "category"]]), 35 / 3)
    pd.testing.assert_frame_equal(frame, original)


def test_dummy_components_clone_nested_params_pipeline_and_cv():
    frame = _portfolio()
    original = frame.copy(deep=True)
    freq, sev = DummyRegressor(), DummyRegressor()
    model = FrequencySeverityModel(freq=freq, sev=sev)
    assert model.get_params()["freq__strategy"] == "mean"
    copied = clone(model).set_params(freq__strategy="mean", sev__strategy="mean")
    assert copied.freq is not freq and copied.sev is not sev
    assert copied.fit(frame) is copied
    _assert_predictions(copied, frame)
    assert not hasattr(freq, "constant_") and not hasattr(sev, "constant_")
    assert not hasattr(clone(copied), "freq_")
    pipeline = Pipeline([("identity", FunctionTransformer()), ("model", clone(model))])
    assert pipeline.fit(frame) is pipeline
    _assert_predictions(pipeline, frame)
    repeated = pd.concat([frame, frame], ignore_index=True)
    scores = cross_val_score(
        pipeline, repeated, repeated.claim_amount / repeated.exposure, cv=KFold(2)
    )
    assert scores.shape == (2,) and np.isfinite(scores).all()
    pd.testing.assert_frame_equal(frame, original)


@pytest.mark.parametrize(
    ("freq_mode", "sev_mode", "wrong_value"),
    [
        ("ignore_weights", "mean", 350 / 27),
        ("mean", "ignore_weights", 10),
        ("mean", "aggregate", 35),
        ("column", "mean", None),
    ],
)
def test_oracle_detects_broken_components(freq_mode, sev_mode, wrong_value):
    frame = _portfolio()
    model = FrequencySeverityModel(freq=RecordingMean(freq_mode), sev=RecordingMean(sev_mode)).fit(
        frame
    )
    if wrong_value is not None:
        np.testing.assert_allclose(model.predict(frame), wrong_value)
    else:
        assert model.predict(frame).shape == (3, 3)
    with pytest.raises(AssertionError):
        _assert_predictions(model, frame)


def test_component_without_cloning_support_fails():
    class Uncloneable:
        def fit(self, X, y, sample_weight=None):
            return self

        def predict(self, X):
            return np.ones(len(X))

    with pytest.raises(TypeError, match="get_params"):
        FrequencySeverityModel(freq=Uncloneable(), sev=DummyRegressor()).fit(_portfolio())


def test_published_component_recipe():
    from pathlib import Path

    document = Path(__file__).resolve().parents[1] / "docs/reference/compatibility.md"
    recipe = document.read_text().split("```python\n", 1)[1].split("```", 1)[0]
    exec(compile(recipe, str(document), "exec"), {})
