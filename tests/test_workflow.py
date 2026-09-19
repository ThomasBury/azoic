"""Tests for azoic.workflow: ExperimentConfig, run_experiment, Run."""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from azoic.data import DatasetSpec
from azoic.metrics import calibration_table, gini, mean_tweedie_deviance, op_ratio, stability_table
from azoic.models import RiskGLM
from azoic.workflow import (
    CategoricalDistribution,
    ExperimentConfig,
    FloatDistribution,
    IntDistribution,
    ModelResult,
    ModelSpec,
    Run,
    TuningSpec,
    _data_fingerprint,
    _deviance_test,
    run_experiment,
)
from tests.conftest import make_synthetic_portfolio


def _write_portfolio(tmp_path: Path, n: int = 4000, seed: int = 42) -> Path:
    p = tmp_path / "portfolio.parquet"
    make_synthetic_portfolio(n=n, seed=seed).to_parquet(p)
    return p


def _basic_yaml(data_path: str, *, with_freq: bool = False, models: str | None = None) -> str:
    if models is None:
        glm_block = """\
  glm-tweedie:
    kind: glm
    params:
      family: tweedie
      link: log
      exposure_col: exposure
      tweedie_power: 1.5
  gbm-tweedie:
    kind: gbm
    params:
      objective: tweedie
      exposure_col: exposure
      tweedie_variance_power: 1.5
      n_estimators: 30
      num_leaves: 15
      learning_rate: 0.05
      random_state: 42
"""
        models = glm_block
    return (
        f"""name: smoke
data_path: {data_path}
spec:
  target: claim_amount
  exposure: exposure
  claim_count: claim_count
features:
  - driver_age
  - vehicle_age
  - region
  - vehicle_brand
split: random
test_size: 0.2
random_state: 42
models:
"""
        + models
    )


def _write_yaml(tmp_path: Path, body: str, name: str = "cfg.yaml") -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# ExperimentConfig / ModelSpec
# ---------------------------------------------------------------------------


def test_modelspec_build_glm_and_gbm() -> None:
    glm = ModelSpec(kind="glm", params={"family": "tweedie", "link": "log"})
    gbm = ModelSpec(kind="gbm", params={"objective": "tweedie"})
    from azoic.models import RiskGBM, RiskGLM

    assert isinstance(glm.build(), RiskGLM)
    assert isinstance(gbm.build(), RiskGBM)


def test_experiment_config_from_yaml_roundtrip(tmp_path: Path) -> None:
    data = _write_portfolio(tmp_path)
    yaml_path = _write_yaml(tmp_path, _basic_yaml(str(data)))
    cfg = ExperimentConfig.from_yaml(yaml_path)
    assert cfg.name == "smoke"
    assert cfg.spec.target == "claim_amount"
    assert cfg.spec.exposure == "exposure"
    assert cfg.spec.claim_count == "claim_count"
    assert set(cfg.models.keys()) == {"glm-tweedie", "gbm-tweedie"}
    assert cfg.models["glm-tweedie"].kind == "glm"
    assert cfg.models["gbm-tweedie"].params["n_estimators"] == 30


def test_from_yaml_anchors_relative_data_path_to_config_dir(tmp_path: Path) -> None:
    sub = tmp_path / "configs"
    sub.mkdir()
    data = _write_portfolio(sub)
    yaml_path = _write_yaml(sub, _basic_yaml(data.name))
    cfg = ExperimentConfig.from_yaml(yaml_path)
    assert cfg.data_path == str(sub / data.name)
    run, _ = run_experiment(cfg, return_estimators=True)
    assert run.n_rows > 0


def test_from_yaml_leaves_absolute_and_uri_data_paths_untouched(tmp_path: Path) -> None:
    data = _write_portfolio(tmp_path)
    yaml_path = _write_yaml(tmp_path, _basic_yaml(str(data)))
    assert ExperimentConfig.from_yaml(yaml_path).data_path == str(data)
    uri_yaml = _write_yaml(tmp_path, _basic_yaml("s3://bucket/portfolio.parquet"), name="s3.yaml")
    assert ExperimentConfig.from_yaml(uri_yaml).data_path == "s3://bucket/portfolio.parquet"


def test_experiment_config_parses_typed_tuning_yaml(tmp_path: Path) -> None:
    data = _write_portfolio(tmp_path)
    body = (
        _basic_yaml(str(data))
        + """tuning:
  n_trials: 30
  calibration_penalty: 2.0
  search_space:
    glm-tweedie:
      alpha:
        type: float
        low: 1.0e-6
        high: 0.1
        log: true
      l1_ratio:
        type: float
        low: 0.0
        high: 1.0
    gbm-tweedie:
      num_leaves:
        type: int
        low: 8
        high: 64
        step: 8
      max_depth:
        type: categorical
        choices: [-1, 4, 6]
"""
    )

    tuning = ExperimentConfig.from_yaml(_write_yaml(tmp_path, body)).tuning

    assert tuning is not None
    assert tuning.n_trials == 30
    assert tuning.calibration_penalty == 2.0
    assert isinstance(tuning.search_space["glm-tweedie"]["alpha"], FloatDistribution)
    assert isinstance(tuning.search_space["gbm-tweedie"]["num_leaves"], IntDistribution)
    assert isinstance(tuning.search_space["gbm-tweedie"]["max_depth"], CategoricalDistribution)


@pytest.mark.parametrize(
    ("distribution", "message"),
    [
        ({"type": "float", "low": 2.0, "high": 1.0}, "low <= high"),
        ({"type": "float", "low": float("inf"), "high": 1.0}, "finite"),
        ({"type": "float", "low": 0.0, "high": 1.0, "step": 0.0}, "positive"),
        (
            {"type": "float", "low": 0.1, "high": 1.0, "step": 0.1, "log": True},
            "mutually exclusive",
        ),
        ({"type": "float", "low": 0.0, "high": 1.0, "log": True}, "positive"),
        ({"type": "int", "low": 2, "high": 1}, "low <= high"),
        ({"type": "int", "low": 1, "high": 2, "step": 0}, "positive"),
        ({"type": "int", "low": 1, "high": 2, "step": 2, "log": True}, "step: 1"),
        ({"type": "int", "low": 0, "high": 2, "log": True}, "positive"),
        ({"type": "categorical", "choices": []}, "at least 1"),
        ({"type": "categorical", "choices": [float("nan")]}, "finite"),
        ({"type": "categorical", "choices": [[1, 2]]}, "valid"),
    ],
)
def test_tuning_distributions_reject_invalid_values(distribution, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        TuningSpec(search_space={"model": {"parameter": distribution}})


@pytest.mark.parametrize(
    "distribution",
    [
        {"type": "float", "low": 0.0, "high": 1.0, "extra": True},
        {"type": "int", "low": 0, "high": 1, "extra": True},
        {"type": "categorical", "choices": [None], "extra": True},
    ],
)
def test_tuning_typed_objects_reject_extra_fields(distribution) -> None:
    with pytest.raises(ValueError, match="extra"):
        TuningSpec(search_space={"model": {"parameter": distribution}})
    with pytest.raises(ValueError, match="extra"):
        TuningSpec(extra=True)


def test_tuning_rejects_empty_unknown_unsupported_and_frequency_severity_spaces() -> None:
    base = {
        "data_path": "ignored",
        "spec": {"target": "claim_amount", "exposure": "exposure", "claim_count": "claim_count"},
        "models": {"glm": ModelSpec(kind="glm")},
    }
    with pytest.raises(ValueError, match="must not be empty"):
        ExperimentConfig(**base, tuning={"search_space": {"glm": {}}})
    with pytest.raises(ValueError, match="unknown models"):
        ExperimentConfig(
            **base,
            tuning={
                "search_space": {"missing": {"alpha": {"type": "float", "low": 0.0, "high": 1.0}}}
            },
        )
    with pytest.raises(ValueError, match="unsupported glm parameters"):
        ExperimentConfig(
            **base,
            tuning={"search_space": {"glm": {"num_leaves": {"type": "int", "low": 4, "high": 8}}}},
        )

    freq_sev = ModelSpec(
        kind="frequency_severity",
        frequency=ModelSpec(kind="glm", params={"family": "poisson"}),
        severity=ModelSpec(kind="glm", params={"family": "gamma"}),
    )
    with pytest.raises(ValueError, match="frequency_severity"):
        ExperimentConfig(
            **{**base, "models": {"frequency-severity": freq_sev}},
            tuning={
                "search_space": {
                    "frequency-severity": {"alpha": {"type": "float", "low": 0.0, "high": 1.0}}
                }
            },
        )


@pytest.mark.parametrize(
    "parameter",
    [
        "family",
        "link",
        "objective",
        "tweedie_power",
        "tweedie_variance_power",
        "exposure_col",
        "random_state",
    ],
)
def test_tuning_rejects_fixed_identity_routing_and_seed_parameters(parameter: str) -> None:
    with pytest.raises(ValueError, match="fixed parameters"):
        ExperimentConfig(
            data_path="ignored",
            spec={"target": "claim_amount", "exposure": "exposure"},
            models={"glm": ModelSpec(kind="glm")},
            tuning={
                "search_space": {"glm": {parameter: {"type": "categorical", "choices": [None]}}}
            },
        )


@pytest.mark.parametrize(
    "tuning",
    [
        {"n_trials": 0},
        {"calibration_penalty": float("inf")},
        {"calibration_penalty": -1.0},
    ],
)
def test_tuning_rejects_invalid_global_settings(tuning) -> None:
    with pytest.raises(ValueError):
        TuningSpec(**tuning)


def test_experiment_config_rejects_extra_fields(tmp_path: Path) -> None:
    body = _basic_yaml("ignored") + "extra_field: 1\n"
    yaml_path = _write_yaml(tmp_path, body)
    with pytest.raises(Exception, match="extra"):
        ExperimentConfig.from_yaml(yaml_path)


def test_experiment_config_features_default_is_all_non_special(tmp_path: Path) -> None:
    df = make_synthetic_portfolio(n=20, seed=1).assign(review_group="review")
    cfg = ExperimentConfig(
        name="x",
        data_path="ignored",
        spec={
            "target": "claim_amount",
            "exposure": "exposure",
            "claim_count": "claim_count",
            "protected_cols": ["review_group"],
        },
        models={"glm-tweedie": ModelSpec(kind="glm", params={"family": "tweedie"})},
    )
    feats = cfg.feature_columns(df)
    assert set(feats) == {"driver_age", "vehicle_age", "region", "vehicle_brand"}


def test_experiment_config_rejects_protected_explicit_feature() -> None:
    with pytest.raises(ValueError, match="special columns"):
        ExperimentConfig(
            data_path="ignored",
            spec={
                "target": "claim_amount",
                "exposure": "exposure",
                "protected_cols": ["review_group"],
            },
            features=["driver_age", "review_group"],
            models={"glm": ModelSpec(kind="glm")},
        )


def test_experiment_config_features_missing_raises(tmp_path: Path) -> None:
    df = make_synthetic_portfolio(n=10, seed=1)
    cfg = ExperimentConfig(
        name="x",
        data_path="ignored",
        spec={"target": "claim_amount", "exposure": "exposure"},
        features=["driver_age", "no_such_col"],
        models={"glm-tweedie": ModelSpec(kind="glm", params={"family": "tweedie"})},
    )
    with pytest.raises(ValueError, match="features not in data"):
        cfg.feature_columns(df)


# ---------------------------------------------------------------------------
# run_experiment
# ---------------------------------------------------------------------------


def test_run_experiment_basic_returns_run_with_results(tmp_path: Path) -> None:
    data = _write_portfolio(tmp_path)
    yaml_path = _write_yaml(tmp_path, _basic_yaml(str(data)))
    cfg = ExperimentConfig.from_yaml(yaml_path)
    run = run_experiment(cfg)

    assert isinstance(run, Run)
    assert len(run.data_fingerprint) == 64
    assert run.n_rows == 4000
    assert run.n_train + run.n_test == run.n_rows
    assert run.n_test == int(round(4000 * 0.2))
    assert set(run.models.keys()) == {"glm-tweedie", "gbm-tweedie"}
    for _name, res in run.models.items():
        assert isinstance(res, ModelResult)
        assert "gini_train" in res.metrics
        assert "gini_test" in res.metrics
        assert "op_ratio_test" in res.metrics
        assert "deviance_test" in res.metrics
        assert np.isfinite(res.metrics["gini_test"])
        assert np.isfinite(res.metrics["deviance_test"])
        assert isinstance(res.calibration_table, pd.DataFrame)
        assert "observed_pure_premium" in res.calibration_table.columns
        assert "o_p_ratio" in res.calibration_table.columns
        assert res.protected_calibration == {}
    # __getitem__ access.


@pytest.mark.parametrize("split", ["random", "temporal"])
def test_run_records_exact_fit_and_holdout_positions(monkeypatch, tmp_path: Path, split) -> None:
    df = make_synthetic_portfolio(n=1000).assign(period=np.arange(1000) % 10)
    df.index = pd.Index(np.arange(1000) * 7 + 10000, name="policy_id")
    data = tmp_path / "indexed.parquet"
    df.to_parquet(data)
    config = ExperimentConfig(
        data_path=str(data),
        spec={"target": "claim_amount", "exposure": "exposure", "time_col": "period"},
        features=["driver_age", "vehicle_age"],
        split=split,
        models={"first": ModelSpec(), "second": ModelSpec()},
    )

    class RecordingEstimator:
        def fit(self, X, y):
            self.fit_frame_ = X.copy()
            self.fit_target_ = y.copy()
            return self

        def predict(self, X):
            return 100.0 + 2.0 * X["driver_age"].to_numpy()

    monkeypatch.setattr(ModelSpec, "build", lambda self, spec: RecordingEstimator())
    run, estimators = run_experiment(config, return_estimators=True)

    assert isinstance(run.train_indices, tuple)
    assert isinstance(run.test_indices, tuple)
    assert all(type(i) is int for i in (*run.train_indices, *run.test_indices))
    assert len(run.train_indices) == run.n_train
    assert len(run.test_indices) == run.n_test
    assert not set(run.train_indices) & set(run.test_indices)
    assert sorted((*run.train_indices, *run.test_indices)) == list(range(run.n_rows))
    with pytest.raises(ValueError, match="frozen"):
        run.test_indices = ()

    train = df.iloc[list(run.train_indices)]
    test = df.iloc[list(run.test_indices)]
    if split == "random":
        perm = np.random.default_rng(config.random_state).permutation(len(df))
        assert run.train_indices == tuple(perm[200:])
        assert run.test_indices == tuple(perm[:200])
    else:
        assert train["period"].max() < test["period"].min()
    for name, estimator in estimators.items():
        pd.testing.assert_frame_equal(estimator.fit_frame_, train[[*run.feature_names, "exposure"]])
        np.testing.assert_array_equal(estimator.fit_target_, train.claim_amount / train.exposure)
        prediction = estimator.predict(test)
        observed, exposure = test.claim_amount.to_numpy(), test.exposure.to_numpy()
        deviance = mean_tweedie_deviance(
            observed / exposure, prediction, sample_weight=exposure, power=1.5
        )
        null_deviance = mean_tweedie_deviance(
            observed / exposure,
            np.full(len(test), observed.sum() / exposure.sum()),
            sample_weight=exposure,
            power=1.5,
        )
        assert run.models[name].metrics == pytest.approx(
            {
                "gini_train": gini(train.claim_amount, estimator.predict(train), train.exposure),
                "gini_test": gini(observed, prediction, exposure),
                "op_ratio_test": op_ratio(observed, prediction, exposure),
                "deviance_test": deviance,
                "d2_test": 1 - deviance / null_deviance,
            }
        )
        pd.testing.assert_frame_equal(
            run.models[name].calibration_table,
            calibration_table(observed, prediction, exposure, n_bins=10),
        )


def test_data_fingerprint_covers_values_columns_dtypes_and_index() -> None:
    df = pd.DataFrame({"x": [1, 2]}, index=[10, 20]).astype({"x": "int64"})
    fingerprint = _data_fingerprint(df)

    assert _data_fingerprint(df.copy()) == fingerprint
    assert _data_fingerprint(df.assign(x=[1, 3])) != fingerprint
    assert _data_fingerprint(df.rename(columns={"x": "y"})) != fingerprint
    assert _data_fingerprint(df.astype({"x": "float64"})) != fingerprint
    assert _data_fingerprint(df.set_axis([11, 20])) != fingerprint


def test_run_experiment_returns_estimators_when_requested(tmp_path: Path) -> None:
    data = _write_portfolio(tmp_path, n=2000)
    yaml_path = _write_yaml(tmp_path, _basic_yaml(str(data)))
    cfg = ExperimentConfig.from_yaml(yaml_path)
    run, ests = run_experiment(cfg, return_estimators=True)
    assert set(ests.keys()) == {"glm-tweedie", "gbm-tweedie"}
    assert hasattr(ests["glm-tweedie"], "predict")
    assert hasattr(ests["gbm-tweedie"], "predict")


def test_interpretation_recipes_run_for_direct_gbm_and_workflow_pipeline(
    tmp_path: Path,
) -> None:
    import matplotlib

    matplotlib.use("Agg")

    import matplotlib.pyplot as plt
    from sklearn.inspection import PartialDependenceDisplay
    from sklearn.pipeline import Pipeline

    from azoic.models import RiskGBM

    df = make_synthetic_portfolio(n=300, seed=13)
    data = tmp_path / "interpretation.parquet"
    df.to_parquet(data)
    features = ["driver_age", "vehicle_age", "region", "vehicle_brand"]
    model_params = {
        "objective": "tweedie",
        "tweedie_variance_power": 1.5,
        "n_estimators": 10,
        "num_leaves": 7,
        "min_child_samples": 5,
        "random_state": 42,
    }
    config = ExperimentConfig(
        name="interpretation",
        data_path=str(data),
        spec={
            "target": "claim_amount",
            "exposure": "exposure",
            "claim_count": "claim_count",
        },
        features=features,
        preprocessing={"binner": {"cols": ["driver_age"], "max_bins": 4}},
        models={"gbm": ModelSpec(kind="gbm", params=model_params)},
    )
    _, estimators = run_experiment(config, return_estimators=True)
    pipeline = estimators["gbm"]
    assert isinstance(pipeline, Pipeline)

    X = df[[*features, "exposure"]]
    y = df["claim_amount"] / df["exposure"]
    direct = RiskGBM(exposure_col="exposure", **model_params).fit(X, y)
    X_explain = X.iloc[:40].copy()
    explanation_features = ["driver_age", "vehicle_age"]
    X_explain[explanation_features] = X_explain[explanation_features].astype(float)
    exposure = X_explain["exposure"].to_numpy()

    for fitted_estimator in (direct, pipeline):
        display = PartialDependenceDisplay.from_estimator(
            fitted_estimator,
            X_explain,
            features=explanation_features,
            kind="both",
            method="brute",
            sample_weight=exposure,
            grid_resolution=5,
            subsample=20,
            random_state=42,
        )
        display.figure_.canvas.draw()
        for result in display.pd_results:
            np.testing.assert_allclose(
                result.average[0],
                np.average(result.individual[0], axis=0, weights=exposure),
            )
        plt.close(display.figure_)

        if isinstance(fitted_estimator, Pipeline):
            model = fitted_estimator[-1]
            X_backend = fitted_estimator[:-1].transform(X_explain)
        else:
            model = fitted_estimator
            X_backend = X_explain
        X_backend = X_backend.drop(columns=model.exposure_col).copy()
        categorical = X_backend.select_dtypes(include=["object", "string"]).columns
        X_backend[categorical] = X_backend[categorical].astype("category")

        contributions = np.asarray(model.backend_.predict(X_backend, pred_contrib=True))
        raw_score = np.asarray(model.backend_.predict(X_backend, raw_score=True))
        assert contributions.shape[1] == len(model.backend_.feature_name_) + 1
        np.testing.assert_allclose(contributions.sum(axis=1), raw_score)
        np.testing.assert_allclose(np.exp(raw_score), fitted_estimator.predict(X_explain))


def test_preprocessing_and_frequency_severity_run_end_to_end(tmp_path: Path) -> None:
    data = _write_portfolio(tmp_path, n=4000)
    models = """\
  direct:
    kind: glm
    params:
      family: tweedie
      link: log
      tweedie_power: 1.5
  freq-sev:
    kind: frequency_severity
    frequency:
      kind: glm
      params:
        family: poisson
        link: log
    severity:
      kind: glm
      params:
        family: gamma
        link: log
"""
    body = _basic_yaml(str(data), models=models).replace(
        "models:\n",
        """preprocessing:
  binner:
    cols: [driver_age, vehicle_age]
    strategy: tree
    max_bins: 4
  grouper:
    cols: [region, vehicle_brand]
    strategy: rare
    min_exposure: 10
models:
""",
    )
    cfg = ExperimentConfig.from_yaml(_write_yaml(tmp_path, body))

    run, estimators = run_experiment(cfg, return_estimators=True)

    from sklearn.pipeline import Pipeline

    from azoic.models import FrequencySeverityModel, RiskGLM

    assert set(run.models) == {"direct", "freq-sev"}
    assert all(isinstance(estimator, Pipeline) for estimator in estimators.values())
    assert isinstance(estimators["direct"].named_steps["model"], RiskGLM)
    assert isinstance(estimators["freq-sev"].named_steps["model"], FrequencySeverityModel)
    assert estimators["direct"].named_steps["model"].exposure_col == "exposure"
    assert np.isfinite(run.models["freq-sev"].metrics["deviance_test"])
    assert np.isfinite(run.models["freq-sev"].metrics["d2_test"])
    assert run.models["freq-sev"].metrics["d2_test"] <= 1.0

    outcome_columns = ["claim_amount", "claim_count"]
    labeled = pd.read_parquet(data)[[*run.feature_names, "exposure", *outcome_columns]]
    unlabeled = labeled.drop(columns=outcome_columns)
    for estimator in estimators.values():
        expected = estimator.predict(labeled)
        actual = estimator.predict(unlabeled)
        np.testing.assert_allclose(actual, expected)
        assert len(actual) == len(unlabeled)
        assert np.isfinite(actual).all()
        assert (actual >= 0).all()


def test_protected_audits_use_outer_test_and_never_fit_columns(tmp_path: Path) -> None:
    n = 1200
    n_test = int(round(n * 0.2))
    df = make_synthetic_portfolio(n=n, seed=19).assign(period=np.arange(n))
    protected_group = np.full(n, "train-only", dtype=object)
    protected_group[-n_test:] = np.resize(
        np.array(["review-a", "review-b", None], dtype=object), n_test
    )
    df = df.assign(
        protected_group=protected_group,
        protected_channel=np.where(np.arange(n) % 2, "broker", "direct"),
    )
    path = tmp_path / "protected.parquet"
    df.to_parquet(path)
    cfg = ExperimentConfig(
        name="protected",
        data_path=str(path),
        spec={
            "target": "claim_amount",
            "exposure": "exposure",
            "claim_count": "claim_count",
            "time_col": "period",
            "protected_cols": ["protected_group", "protected_channel"],
        },
        preprocessing={"binner": {"cols": ["driver_age"], "max_bins": 4}},
        split="temporal",
        test_size=0.2,
        models={
            "glm": ModelSpec(
                kind="glm",
                params={"family": "tweedie", "link": "log", "tweedie_power": 1.5},
            )
        },
    )

    run, estimators = run_experiment(cfg, return_estimators=True)

    assert set(run.feature_names) == {"driver_age", "vehicle_age", "region", "vehicle_brand"}
    result = run.models["glm"]
    assert set(result.protected_calibration) == {"protected_group", "protected_channel"}
    group_table = result.protected_calibration["protected_group"]
    assert "train-only" not in set(group_table["group"].dropna())
    assert set(group_table["group"].dropna()) == {"review-a", "review-b"}
    assert group_table["group"].isna().sum() == 1

    held_out = df.tail(n_test)
    for table in result.protected_calibration.values():
        assert np.isclose(table["exposure"].sum(), held_out["exposure"].sum())
        assert np.isclose(table["claim_amount"].sum(), held_out["claim_amount"].sum())
        assert np.isclose(
            table["predicted_claim_amount"].sum(),
            result.calibration_table["predicted_claim_amount"].sum(),
        )

    pipeline = estimators["glm"]
    for fitted in (pipeline, pipeline.named_steps["binner"], pipeline.named_steps["model"]):
        assert not set(cfg.spec.protected_cols) & set(fitted.feature_names_in_)


def test_run_experiment_temporal_split_requires_time_col(tmp_path: Path) -> None:
    data = _write_portfolio(tmp_path, n=2000)
    body = _basic_yaml(str(data)).replace("split: random", "split: temporal")
    yaml_path = _write_yaml(tmp_path, body)
    cfg = ExperimentConfig.from_yaml(yaml_path)
    with pytest.raises(ValueError, match="time_col"):
        run_experiment(cfg)


def test_run_experiment_temporal_split_with_time_col(tmp_path: Path) -> None:
    df = make_synthetic_portfolio(n=2000, seed=1)
    rng = np.random.default_rng(7)
    df = df.assign(day=rng.integers(0, 365, size=len(df)))
    # Temporal split sorts ascending; use a cutoff at the 80th percentile of days.
    p = tmp_path / "portfolio.parquet"
    df.to_parquet(p)
    body = f"""name: smoke
data_path: {p}
spec:
  target: claim_amount
  exposure: exposure
  claim_count: claim_count
  time_col: day
features:
  - driver_age
  - vehicle_age
  - region
  - vehicle_brand
split: temporal
test_size: 0.2
random_state: 42
models:
  glm-tweedie:
    kind: glm
    params:
      family: tweedie
      link: log
      exposure_col: exposure
      tweedie_power: 1.5
"""
    yaml_path = _write_yaml(tmp_path, body)
    cfg = ExperimentConfig.from_yaml(yaml_path)
    run = run_experiment(cfg)
    assert run.n_test >= int(round(2000 * 0.2))
    assert run.n_train + run.n_test == 2000
    assert run.models["glm-tweedie"].metrics["gini_test"] >= 0.0


def test_run_experiment_pure_premium_op_ratio_near_one(tmp_path: Path) -> None:
    """In-sample adequacy: op_ratio on test should be close to 1.0 for a Tweedie
    GLM with exposure as weight (no exposure leakage, weight convention ok)."""
    data = _write_portfolio(tmp_path)
    yaml_path = _write_yaml(tmp_path, _basic_yaml(str(data)))
    cfg = ExperimentConfig.from_yaml(yaml_path)
    run = run_experiment(cfg)
    op = run.models["glm-tweedie"].metrics["op_ratio_test"]
    # Tw1 tolerance matches the M3 acceptance test -- portfolio adequacy held.
    assert 0.85 <= op <= 1.15, f"op_ratio_test drift: {op:.4f}"


def test_run_experiment_empty_dataset_raises(tmp_path: Path) -> None:
    empty = tmp_path / "empty.parquet"
    pd.DataFrame(
        {
            "exposure": pd.Series([], dtype=float),
            "claim_count": pd.Series([], dtype=int),
            "claim_amount": pd.Series([], dtype=float),
            "driver_age": pd.Series([], dtype=int),
        }
    ).to_parquet(empty)
    yaml_path = _write_yaml(
        tmp_path,
        _basic_yaml(str(empty)).replace("models:\n", "models:\n"),
    )
    cfg = ExperimentConfig.from_yaml(yaml_path)
    with pytest.raises(ValueError, match="empty"):
        run_experiment(cfg)


# ---------------------------------------------------------------------------


def test_deviance_test_is_exposure_weighted_tweedie_power_1_5() -> None:
    from sklearn.metrics import mean_tweedie_deviance

    observed = np.array([0.0, 1.0, 4.0])
    predicted = np.array([0.5, 1.5, 3.0])
    exposure = np.array([1.0, 2.0, 5.0])
    actual = _deviance_test(
        obs_rate=observed,
        pred_rate=predicted,
        exposure=exposure,
    )
    expected = mean_tweedie_deviance(
        observed,
        predicted,
        sample_weight=exposure,
        power=1.5,
    )
    squared_error = mean_tweedie_deviance(
        observed,
        predicted,
        sample_weight=exposure,
        power=0,
    )
    assert actual == pytest.approx(expected)
    assert actual != pytest.approx(squared_error)


def test_experiment_config_rejects_empty_models_duplicate_and_special_features() -> None:
    base = {
        "data_path": "ignored",
        "spec": {"target": "claim_amount", "exposure": "exposure"},
    }
    with pytest.raises(ValueError, match="models"):
        ExperimentConfig(**base, models={})
    with pytest.raises(ValueError, match="unique"):
        ExperimentConfig(
            **base,
            features=["driver_age", "driver_age"],
            models={"glm": ModelSpec()},
        )
    with pytest.raises(ValueError, match="special"):
        ExperimentConfig(
            **base,
            features=["driver_age", "exposure"],
            models={"glm": ModelSpec()},
        )


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("exposure", 0.0, "positive finite"),
        ("exposure", np.inf, "positive finite"),
        ("claim_amount", -1.0, "non-negative finite"),
        ("claim_amount", np.inf, "non-negative finite"),
        ("claim_count", -1.0, "non-negative finite"),
        ("claim_count", np.inf, "non-negative finite"),
    ],
)
def test_run_experiment_rejects_invalid_portfolio_values(
    tmp_path: Path,
    column: str,
    value: float,
    message: str,
) -> None:
    df = make_synthetic_portfolio(n=100, seed=42)
    if column == "claim_count":
        df[column] = df[column].astype(float)
    df.loc[df.index[0], column] = value
    data = tmp_path / "invalid.parquet"
    df.to_parquet(data)
    config = ExperimentConfig.from_yaml(_write_yaml(tmp_path, _basic_yaml(str(data))))
    with pytest.raises(ValueError, match=message):
        run_experiment(config)


def test_run_experiment_rejects_sub_day_exposure(tmp_path: Path) -> None:
    """Tiny exposures blow up claim_amount/exposure rates and destabilize
    GLMs; the portfolio boundary rejects anything below one day (1/366)."""
    df = make_synthetic_portfolio(n=100, seed=42)
    df.loc[df.index[0], "exposure"] = 0.001
    df.loc[df.index[0], "claim_amount"] = 0.0
    df.loc[df.index[0], "claim_count"] = 0.0
    data = tmp_path / "subday.parquet"
    df.to_parquet(data)
    config = ExperimentConfig.from_yaml(_write_yaml(tmp_path, _basic_yaml(str(data))))
    with pytest.raises(ValueError, match="1/366"):
        run_experiment(config)


def test_run_experiment_rejects_inconsistent_claim_rows(tmp_path: Path) -> None:
    df = make_synthetic_portfolio(n=100, seed=42)
    df.loc[df.index[0], ["claim_count", "claim_amount"]] = [0, 1.0]
    data = tmp_path / "inconsistent.parquet"
    df.to_parquet(data)
    config = ExperimentConfig.from_yaml(_write_yaml(tmp_path, _basic_yaml(str(data))))
    with pytest.raises(ValueError, match="zero or positive together"):
        run_experiment(config)


def test_m5_acceptance_example_config_runs_end_to_end(tmp_path: Path) -> None:
    data = _write_portfolio(tmp_path, n=4000)
    config = ExperimentConfig.from_yaml(_write_yaml(tmp_path, _basic_yaml(str(data))))
    run = run_experiment(config)

    for name, result in run.models.items():
        assert result.metrics["gini_test"] > 0.0, name
        assert 0.5 <= result.metrics["op_ratio_test"] <= 1.5
        assert len(result.calibration_table) >= 2
        assert {
            "exposure",
            "claim_amount",
            "observed_pure_premium",
            "predicted_pure_premium",
            "o_p_ratio",
        }.issubset(result.calibration_table.columns)


@pytest.mark.parametrize("test_rates", [[0.0, 0.0, 0.0], [4.0, 4.0, 4.0], [0.0, 4.0, 12.0]])
def test_temporal_test_d2_matches_period_baseline(tmp_path, test_rates) -> None:
    exposure = np.array([0.5, 1.0, 2.0] * 4)
    rates = np.array([0.0, 8.0, 12.0] * 3 + test_rates)
    df = pd.DataFrame(
        {
            "feature": np.arange(12) % 3,
            "period": np.repeat(np.arange(4), 3),
            "exposure": exposure,
            "claim_amount": rates * exposure,
            "claim_count": (rates > 0).astype(int),
        }
    )
    path = tmp_path / "temporal.parquet"
    df.to_parquet(path)
    config = ExperimentConfig(
        data_path=str(path),
        spec={
            "target": "claim_amount",
            "exposure": "exposure",
            "claim_count": "claim_count",
            "time_col": "period",
        },
        features=["feature"],
        split="temporal",
        test_size=0.25,
        models={"glm": ModelSpec(params={"alpha": 1.0})},
    )
    run, estimators = run_experiment(config, return_estimators=True)
    test = df.iloc[list(run.test_indices)]
    assert run.test_indices == (9, 10, 11)
    prediction = estimators["glm"].predict(test[["feature", "exposure"]])
    result = run.models["glm"]
    period = stability_table(
        test.claim_amount, prediction, test.exposure, periods=test.period
    ).iloc[0]
    assert np.isfinite(result.metrics["deviance_test"])
    assert result.metrics["deviance_test"] == pytest.approx(period.deviance)
    assert result.metrics["op_ratio_test"] == pytest.approx(period.o_p_ratio)
    assert result.metrics["gini_test"] == pytest.approx(period.gini)
    if len(set(test_rates)) == 1:
        assert np.isnan(result.metrics["d2_test"])
        assert np.isnan(period.d2)
    else:
        null_deviance = mean_tweedie_deviance(
            test_rates,
            np.full(3, test.claim_amount.sum() / test.exposure.sum()),
            sample_weight=test.exposure,
            power=1.5,
        )
        assert result.metrics["d2_test"] == pytest.approx(
            1 - result.metrics["deviance_test"] / null_deviance
        )
        assert result.metrics["d2_test"] == pytest.approx(period.d2)
    if not any(test_rates):
        assert result.metrics["op_ratio_test"] == 0.0
    np.testing.assert_allclose(
        result.calibration_table[["exposure", "claim_amount", "predicted_claim_amount"]].sum(),
        [test.exposure.sum(), test.claim_amount.sum(), np.dot(prediction, test.exposure)],
    )


def test_tutorial_freezes_all_training_factors_and_labels_holdout_metrics(monkeypatch, tmp_path):
    from azoic.plots import model_colors
    from azoic.reporting import comparison_table

    portfolio = make_synthetic_portfolio(n=600)
    portfolio.index = pd.Index(np.arange(len(portfolio)) * 7 + 10000, name="policy_id")
    path = tmp_path / "tutorial.parquet"
    portfolio.to_parquet(path)
    names = [
        "direct-tweedie-glm",
        "tweedie-lightgbm-tariff",
        "tweedie-lightgbm",
    ]
    features = ["driver_age", "vehicle_age"]

    class FixedEstimator:
        def __init__(self, scale):
            self.scale = scale

        def fit(self, X, y):
            return self

        def predict(self, X):
            return self.scale * (100.0 + X["driver_age"].to_numpy())

    monkeypatch.setattr(ModelSpec, "build", lambda self, spec: FixedEstimator(self.params["scale"]))
    config = ExperimentConfig(
        data_path=str(path),
        spec={"target": "claim_amount", "exposure": "exposure", "claim_count": "claim_count"},
        features=features,
        models={name: ModelSpec(params={"scale": i + 1}) for i, name in enumerate(names)},
    )
    run, estimators = run_experiment(config, return_estimators=True)
    train = portfolio.iloc[list(run.train_indices)]
    test = portfolio.iloc[list(run.test_indices)]
    namespace = {
        "np": np,
        "pd": pd,
        "portfolio": portfolio,
        "features": features,
        "estimators": estimators,
        "glm_run": run,
        "gbm_run": run,
        "runs": [run],
        "train_idx": np.array(run.train_indices),
        "test_idx": np.array(run.test_indices),
        "display": lambda value: None,
        "calibration_table": calibration_table,
        "gini": gini,
        "op_ratio": op_ratio,
        "mean_tweedie_deviance": mean_tweedie_deviance,
        "model_colors": model_colors,
        "comparison_table": comparison_table,
        "train_frame": train.copy(),
        "test_frame": test.copy(),
        "y_train": train["claim_amount"].to_numpy(),
        "w_train": train["exposure"].to_numpy(),
        "y_test": test["claim_amount"].to_numpy(),
        "w_test": test["exposure"].to_numpy(),
        "raw_predict_columns": [*features, "exposure"],
    }
    examples = Path(__file__).parents[1] / "examples"
    shared_cells = re.findall(
        r"```\{python\}\n(.*?)\n```",
        (examples / "_shared.qmd").read_text(),
        flags=re.DOTALL,
    )
    exec(next(c for c in shared_cells if "def holdout_diagnostics" in c), namespace)
    diagnostics_cells = re.findall(
        r"```\{python\}\n(.*?)\n```",
        (examples / "03-diagnostics.qmd").read_text(),
        flags=re.DOTALL,
    )
    recalibration_code = next(
        cell for cell in diagnostics_cells if cell.startswith("recalibration_factors =")
    )
    holdout_code = next(
        cell for cell in diagnostics_cells if cell.startswith("raw_test_predictions: dict")
    )
    exec(recalibration_code, namespace)
    factors = namespace["recalibration_factors"].copy()
    assert set(factors) == set(names)
    for name, estimator in estimators.items():
        expected = train.claim_amount.sum() / np.dot(train.exposure, estimator.predict(train))
        assert factors[name] == pytest.approx(expected)
    namespace["y_test"] = namespace["y_test"] * 100
    exec(recalibration_code, namespace)
    assert namespace["recalibration_factors"] == factors
    namespace["y_test"] = test["claim_amount"].to_numpy()
    exec(holdout_code, namespace)
    table = namespace["holdout_metrics"].set_index(["model", "prediction_scale"])
    assert len(table) == 2 * len(names)
    for name in names:
        raw = table.loc[(name, "raw")]
        adjusted = table.loc[(name, "training O/P adjusted")]
        assert raw.op_ratio_test == pytest.approx(run.models[name].metrics["op_ratio_test"])
        assert adjusted.op_ratio_test == pytest.approx(raw.op_ratio_test / factors[name])
        assert adjusted.gini_test == pytest.approx(raw.gini_test)
        prediction = namespace["test_predictions"][name]
        np.testing.assert_allclose(
            prediction, factors[name] * namespace["raw_test_predictions"][name]
        )
        expected = mean_tweedie_deviance(
            test.claim_amount / test.exposure, prediction, sample_weight=test.exposure, power=1.5
        )
        assert adjusted.deviance_test == pytest.approx(expected)

    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import FunctionTransformer

    from azoic.tariff import apply_tariff

    workbook_tariff = {"base_rate": 125.0, "numeric": {"driver_age": 0.01}, "categorical": {}}
    namespace.update(
        {
            "apply_tariff": apply_tariff,
            "workbook_tariff": workbook_tariff,
            "distilled_pipeline": Pipeline([("identity", FunctionTransformer()), ("model", None)]),
            "fit_X": train,
            "teacher_rate": namespace["raw_test_predictions"][names[1]],
            "workbook_rate": apply_tariff(workbook_tariff, test),
            "ARTIFACT_DIR": tmp_path,
        }
    )
    tariff_cells = re.findall(
        r"```\{python\}\n(.*?)\n```",
        (examples / "04-scoring-tariff.qmd").read_text(),
        flags=re.DOTALL,
    )
    final_code = next(cell for cell in tariff_cells if cell.startswith("workbook_train_rate ="))
    exec(final_code, namespace)
    workbook_factor = train.claim_amount.sum() / np.dot(
        train.exposure, apply_tariff(workbook_tariff, train)
    )
    assert namespace["workbook_factor"] == pytest.approx(workbook_factor)
    assert not np.isclose(workbook_factor, factors[names[1]])
    final_table = namespace["final_metrics"].set_index(["model", "prediction_scale"])
    assert len(final_table) == 8
    null_deviance = mean_tweedie_deviance(
        test.claim_amount / test.exposure,
        np.full(len(test), test.claim_amount.sum() / test.exposure.sum()),
        sample_weight=test.exposure,
        power=1.5,
    )
    for name, raw_prediction in namespace["final_raw_predictions"].items():
        for scale in ["raw", "training O/P adjusted"]:
            prediction = raw_prediction.copy()
            if scale != "raw":
                prediction *= namespace["final_factors"][name]
            row = final_table.loc[(name, scale)]
            deviance = mean_tweedie_deviance(
                test.claim_amount / test.exposure,
                prediction,
                sample_weight=test.exposure,
                power=1.5,
            )
            assert row.deviance_test == pytest.approx(deviance)
            assert row.d2_test == pytest.approx(1 - deviance / null_deviance)
            assert row.predicted_claim_amount == pytest.approx(prediction @ test.exposure)
            assert row.observed_claim_amount == pytest.approx(test.claim_amount.sum())
            assert row.exposure == pytest.approx(test.exposure.sum())
    namespace["y_test"] = namespace["y_test"] * 100
    exec(final_code, namespace)
    assert namespace["workbook_factor"] == pytest.approx(workbook_factor)
    np.testing.assert_array_equal(namespace["workbook_rate"], apply_tariff(workbook_tariff, test))


# ---------------------------------------------------------------------------
# Component warnings, exposure contradiction, effective params (M32)
# ---------------------------------------------------------------------------


def test_modelspec_warns_on_ill_posed_freq_sev_components() -> None:
    with pytest.warns(UserWarning, match="negative support"):
        ModelSpec.model_validate(
            {
                "kind": "frequency_severity",
                "frequency": {"kind": "glm", "params": {"family": "normal"}},
                "severity": {"kind": "gbm", "params": {"objective": "regression_l1"}},
            }
        )


def test_modelspec_accepts_poisson_gamma_freq_sev_without_warning() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        ModelSpec.model_validate(
            {
                "kind": "frequency_severity",
                "frequency": {"kind": "glm", "params": {"family": "poisson"}},
                "severity": {"kind": "glm", "params": {"family": "gamma"}},
            }
        )


def test_modelspec_build_rejects_contradictory_exposure_col() -> None:
    from azoic.data import DatasetSpec

    spec = DatasetSpec(target="claim_amount", exposure="exposure")
    bad = ModelSpec(kind="glm", params={"family": "poisson", "exposure_col": "wrong"})
    with pytest.raises(ValueError, match="contradicts"):
        bad.build(spec)
    good = ModelSpec(kind="glm", params={"family": "poisson", "exposure_col": "exposure"})
    assert good.build(spec).exposure_col == "exposure"


def test_run_records_effective_params(tmp_path: Path) -> None:
    """Recorded params must reflect the fitted estimator: the spec-driven
    exposure_col appears even when YAML omits it, and freq-sev records the
    special columns it was built with."""
    data = _write_portfolio(tmp_path)
    yaml_path = _write_yaml(
        tmp_path,
        _basic_yaml(
            str(data),
            models="""\
  glm-poisson:
    kind: glm
    params:
      family: poisson
  freq-sev:
    kind: frequency_severity
    frequency:
      kind: glm
      params:
        family: poisson
    severity:
      kind: glm
      params:
        family: gamma
""",
        ),
    )
    run = run_experiment(ExperimentConfig.from_yaml(yaml_path))
    assert run.models["glm-poisson"].params["exposure_col"] == "exposure"
    freq_sev = run.models["freq-sev"].params
    assert freq_sev["exposure_col"] == "exposure"
    assert freq_sev["claim_count_col"] == "claim_count"
    assert freq_sev["claim_amount_col"] == "claim_amount"
    assert freq_sev["frequency"]["params"]["family"] == "poisson"


# ---------------------------------------------------------------------------
# frequency_severity params are forwarded, not silently dropped (M33)
# ---------------------------------------------------------------------------


def _fsm_spec(**params):
    return ModelSpec(
        kind="frequency_severity",
        params=params,
        frequency={"kind": "glm", "params": {"family": "poisson"}},
        severity={"kind": "glm", "params": {"family": "gamma"}},
    )


def test_modelspec_freq_sev_forwards_matching_params() -> None:
    """A matching special-column param is applied to the constructor and
    recorded identically -- recorded params can never name a phantom key."""
    spec = DatasetSpec(target="claim_amount", exposure="exposure", claim_count="claim_count")
    ms = _fsm_spec(exposure_col="exposure")
    est = ms.build(spec)
    assert est.exposure_col == "exposure"
    assert ms.effective_params(spec)["exposure_col"] == "exposure"


@pytest.mark.parametrize(
    ("key", "value"),
    [("exposure_col", "wrong"), ("claim_count_col", "wrong"), ("claim_amount_col", "wrong")],
)
def test_modelspec_freq_sev_rejects_contradictory_special_columns(key, value) -> None:
    spec = DatasetSpec(target="claim_amount", exposure="exposure", claim_count="claim_count")
    with pytest.raises(ValueError, match="contradicts"):
        _fsm_spec(**{key: value}).build(spec)


def test_modelspec_freq_sev_unknown_param_fails_loudly() -> None:
    """Unknown params previously vanished silently while being recorded."""
    spec = DatasetSpec(target="claim_amount", exposure="exposure", claim_count="claim_count")
    with pytest.raises(TypeError, match="bogus_param"):
        _fsm_spec(bogus_param=1).build(spec)


def test_modelspec_freq_sev_rejects_reserved_component_keys() -> None:
    spec = DatasetSpec(target="claim_amount", exposure="exposure", claim_count="claim_count")
    with pytest.raises(ValueError, match="reserved"):
        _fsm_spec(freq=RiskGLM()).build(spec)
