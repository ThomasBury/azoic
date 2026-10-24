"""Tests for azoic.tune.tune_experiment (optuna search, v0.2 part 1 / M7).

optuna is provided by the ``tune`` extra. These tests run real optuna studies
on the synthetic portfolio (no server needed -- optuna is in-memory by
default). The M7 acceptance test asserts a tuned ``Run`` is a canonical
``run_experiment`` output whose models carry finite Gini / O-P ratio /
deviance and a populated calibration table.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

optuna = pytest.importorskip("optuna")  # skip the whole module if tune extra absent

from azoic.tune import (  # noqa: E402
    TuneResult,
    _objective_value,
    tune_experiment,
)
from azoic.workflow import (  # noqa: E402
    ExperimentConfig,
    ModelResult,
    ModelSpec,
    PreprocessingSpec,
    Run,
    TuningSpec,
    _split_indices,
    run_experiment,
)
from tests.conftest import make_synthetic_portfolio  # noqa: E402


def _config(
    tmp_path: Path,
    *,
    models: dict[str, ModelSpec],
    name: str = "smoke",
    tuning: TuningSpec | dict | None = None,
) -> ExperimentConfig:
    p = tmp_path / "portfolio.parquet"
    make_synthetic_portfolio(n=2000, seed=42).to_parquet(p)
    return ExperimentConfig(
        name=name,
        data_path=str(p),
        spec={"target": "claim_amount", "exposure": "exposure", "claim_count": "claim_count"},
        features=["driver_age", "vehicle_age", "region", "vehicle_brand"],
        split="random",
        test_size=0.2,
        random_state=42,
        models=models,
        tuning=tuning,
    )


def _glm() -> ModelSpec:
    return ModelSpec(
        kind="glm",
        params={
            "family": "tweedie",
            "link": "log",
            "exposure_col": "exposure",
            "tweedie_power": 1.5,
        },
    )


def _gbm() -> ModelSpec:
    return ModelSpec(
        kind="gbm",
        params={
            "objective": "tweedie",
            "exposure_col": "exposure",
            "tweedie_variance_power": 1.5,
            "n_estimators": 20,
            "num_leaves": 15,
            "random_state": 42,
        },
    )


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("exposure", 0.0, "positive finite"),
        ("exposure", 0.001, "1/366"),
        ("exposure", np.nan, "positive finite"),
        ("claim_amount", -1.0, "non-negative finite"),
        ("claim_amount", np.inf, "non-negative finite"),
        ("claim_count", -1.0, "non-negative finite"),
        ("claim_count", np.inf, "non-negative finite"),
        ("claim_count", 0.0, "zero or positive together"),
    ],
)
def test_tuning_rejects_invalid_portfolio_before_trials(tmp_path, column, value, message):
    cfg = _config(tmp_path, models={"glm": _glm()})
    df = pd.DataFrame(
        {"exposure": [1.0, 1.0], "claim_amount": [10.0, 20.0], "claim_count": [1.0, 2.0]}
    )
    df.loc[0, column] = value
    original = df.copy(deep=True)
    with pytest.raises(ValueError, match=message):
        tune_experiment(cfg, df=df, n_trials=1)
    pd.testing.assert_frame_equal(df, original)


def test_tune_in_memory_matches_file_without_loading(tmp_path, monkeypatch):
    from sklearn.pipeline import Pipeline

    cfg = _config(
        tmp_path, models={"glm": _glm(), "gbm": _gbm().model_copy(update={"preprocess": False})}
    )
    cfg.preprocessing = PreprocessingSpec(
        binner={"cols": ["driver_age"], "max_bins": 3},
        grouper={"cols": ["region"], "max_groups": 2},
    )
    expected = tune_experiment(cfg, n_trials=1)
    df = pd.read_parquet(cfg.data_path)
    original = df.copy(deep=True)

    def reject_load(*args, **kwargs):
        raise AssertionError("in-memory tuning must not load a file")

    monkeypatch.setattr("azoic.tune.load_data", reject_load)
    actual = tune_experiment(cfg, df=df, n_trials=1, return_estimators=True)
    assert actual.best_params == expected.best_params
    assert actual.run.data_fingerprint == expected.run.data_fingerprint
    assert actual.run.train_indices == expected.run.train_indices
    assert actual.run.test_indices == expected.run.test_indices
    assert actual.run.models["glm"].metrics == pytest.approx(expected.run.models["glm"].metrics)
    assert isinstance(actual.estimators["glm"], Pipeline)
    assert not isinstance(actual.estimators["gbm"], Pipeline)
    assert actual.run.models["gbm"].metrics == pytest.approx(expected.run.models["gbm"].metrics)
    pd.testing.assert_frame_equal(df, original)


# ---------------------------------------------------------------------------
# _objective_value
# ---------------------------------------------------------------------------


def test_objective_value_combines_deviance_and_calibration_penalty() -> None:
    m = {"deviance_test": 100.0, "op_ratio_test": 1.1}
    # 100 + 0.5 * |1 - 1.1| = 100.05
    assert _objective_value(m, calibration_penalty=0.5) == pytest.approx(100.05)


def test_objective_value_returns_inf_when_op_ratio_is_nan() -> None:
    """op_ratio_test NaN (pred_total == 0) -> worthless trial; optuna rejects NaN
    (4.x), so we return inf instead."""
    m = {"deviance_test": 10.0, "op_ratio_test": float("nan")}
    out = _objective_value(m, calibration_penalty=1.0)
    assert out == float("inf")


def test_objective_value_missing_deviance_is_inf() -> None:
    m = {"op_ratio_test": 1.0}
    assert _objective_value(m, calibration_penalty=1.0) == float("inf")


# ---------------------------------------------------------------------------
# tune_experiment -- happy paths
# ---------------------------------------------------------------------------


def test_tune_experiment_glm_returns_tune_result_with_best_params(tmp_path: Path) -> None:
    cfg = _config(tmp_path, models={"glm-tweedie": _glm()})
    result = tune_experiment(cfg, n_trials=3, calibration_penalty=1.0)

    assert isinstance(result, TuneResult)
    assert result.n_trials == 3
    assert set(result.best_params) == {"glm-tweedie"}
    # Only sampled hyperparams land in best_params; identity params stay on Run.
    assert set(result.best_params["glm-tweedie"]) == {"alpha", "l1_ratio"}
    assert isinstance(result.best_values["glm-tweedie"], float)
    assert np.isfinite(result.best_values["glm-tweedie"])


def test_tune_experiment_gbm_search_space_only_samples_structure(tmp_path: Path) -> None:
    cfg = _config(tmp_path, models={"gbm-tweedie": _gbm()})
    result = tune_experiment(cfg, n_trials=2)
    sampled = set(result.best_params["gbm-tweedie"])
    assert sampled == {
        "num_leaves",
        "learning_rate",
        "n_estimators",
        "min_child_samples",
        "reg_alpha",
        "reg_lambda",
    }
    # Identity params (objective / exposure_col / tweedie_variance_power /
    # random_state) must NOT appear in best_params.
    for forbidden in ("objective", "exposure_col", "tweedie_variance_power", "random_state"):
        assert forbidden not in sampled


def test_custom_space_replaces_one_model_defaults_and_leaves_sibling_defaults(
    tmp_path: Path,
) -> None:
    cfg = _config(
        tmp_path,
        models={"glm-tweedie": _glm(), "gbm-tweedie": _gbm()},
        tuning={
            "n_trials": 2,
            "search_space": {
                "gbm-tweedie": {
                    "learning_rate": {
                        "type": "float",
                        "low": 0.01,
                        "high": 0.1,
                        "log": True,
                    },
                    "num_leaves": {"type": "int", "low": 8, "high": 16, "step": 8},
                    "max_depth": {"type": "categorical", "choices": [-1, 4]},
                }
            },
        },
    )

    result = tune_experiment(cfg)

    assert set(result.best_params["gbm-tweedie"]) == {
        "learning_rate",
        "num_leaves",
        "max_depth",
    }
    assert set(result.best_params["glm-tweedie"]) == {"alpha", "l1_ratio"}


def test_omitted_tuning_reproduces_default_space_and_seeded_results(tmp_path: Path) -> None:
    models = {"glm-tweedie": _glm()}
    omitted = _config(tmp_path, models=models)
    empty = omitted.model_copy(update={"tuning": TuningSpec()})

    original = tune_experiment(omitted, n_trials=3, random_state=9)
    configured = tune_experiment(empty, n_trials=3, random_state=9)

    assert original.best_params == configured.best_params
    assert original.best_values == pytest.approx(configured.best_values, rel=1e-9)


@pytest.mark.parametrize(
    ("configured", "kwargs", "trials", "penalty"),
    [
        (True, {"n_trials": 4, "calibration_penalty": 5.0}, 4, 5.0),
        (True, {}, 2, 3.0),
        (False, {}, 20, 1.0),
    ],
)
def test_python_tuning_precedence(monkeypatch, tmp_path, configured, kwargs, trials, penalty):
    studies = []
    create_study = optuna.create_study

    def record_study(**kwargs):
        study = create_study(**kwargs)
        studies.append(study)
        return study

    monkeypatch.setattr(optuna, "create_study", record_study)
    config = _config(
        tmp_path,
        models={"glm-tweedie": _glm()},
        tuning={"n_trials": 2, "calibration_penalty": 3.0} if configured else None,
    )
    result = tune_experiment(config, **kwargs)
    assert result.n_trials == len(studies[0].trials) == trials
    df = pd.read_parquet(config.data_path)
    outer_training = df.iloc[list(result.run.train_indices)]
    inner_run = run_experiment(result.run.config, df=outer_training)
    metrics = inner_run.models["glm-tweedie"].metrics
    assert result.best_values["glm-tweedie"] == pytest.approx(
        metrics["deviance_test"] + penalty * abs(1 - metrics["op_ratio_test"])
    )


def test_tune_experiment_preserves_yaml_identity_params_in_final_run(
    tmp_path: Path,
) -> None:
    cfg = _config(tmp_path, models={"glm-tweedie": _glm(), "gbm-tweedie": _gbm()})
    result = tune_experiment(cfg, n_trials=2)
    # The final Run should look exactly like a direct run_experiment Run --
    # identity params from the YAML survive the merge.
    glm_params = result.run.models["glm-tweedie"].params
    gbm_params = result.run.models["gbm-tweedie"].params
    assert glm_params["family"] == "tweedie"
    assert glm_params["link"] == "log"
    assert glm_params["exposure_col"] == "exposure"
    assert glm_params["tweedie_power"] == 1.5
    assert gbm_params["objective"] == "tweedie"
    assert gbm_params["tweedie_variance_power"] == 1.5  # PRD rule 4 never broken by search.


def test_tune_experiment_return_estimators(tmp_path: Path) -> None:
    cfg = _config(tmp_path, models={"glm-tweedie": _glm()})
    result = tune_experiment(cfg, n_trials=2, return_estimators=True)
    assert isinstance(result, TuneResult)
    assert set(result.estimators) == {"glm-tweedie"}
    # The estimator is fitted (has coef_ from glum).
    assert hasattr(result.estimators["glm-tweedie"], "coef_")


def test_tune_experiment_reproducible_with_random_state(tmp_path: Path) -> None:
    cfg = _config(
        tmp_path,
        models={"glm-tweedie": _glm()},
        tuning={
            "search_space": {
                "glm-tweedie": {
                    "alpha": {
                        "type": "float",
                        "low": 1e-5,
                        "high": 0.1,
                        "log": True,
                    },
                    "l1_ratio": {"type": "categorical", "choices": [0.0, 0.5, 1.0]},
                }
            }
        },
    )
    a = tune_experiment(cfg, n_trials=3, random_state=42)
    b = tune_experiment(cfg, n_trials=3, random_state=42)
    assert a.best_params == b.best_params
    # Best params are identical (TPESampler(seed=...) is deterministic). The
    # best VALUE carries ULP noise from BLAS scoring of glum/lightgbm -- assert
    # relative tolerance instead of strict equality.
    for k in a.best_values:
        assert a.best_values[k] == pytest.approx(b.best_values[k], rel=1e-9)


def test_tune_experiment_rejects_zero_trials(tmp_path: Path) -> None:
    cfg = _config(tmp_path, models={"glm-tweedie": _glm()})
    with pytest.raises(ValueError, match="n_trials"):
        tune_experiment(cfg, n_trials=0)


@pytest.mark.parametrize("penalty", [-1.0, float("inf"), float("nan")])
def test_tune_experiment_rejects_invalid_calibration_penalty(
    tmp_path: Path, penalty: float
) -> None:
    cfg = _config(tmp_path, models={"glm-tweedie": _glm()})
    with pytest.raises(ValueError, match="calibration_penalty"):
        tune_experiment(cfg, n_trials=1, calibration_penalty=penalty)


def test_tune_experiment_rejects_frequency_severity(tmp_path: Path) -> None:
    freq_sev = ModelSpec(
        kind="frequency_severity",
        frequency=ModelSpec(kind="glm", params={"family": "poisson", "link": "log"}),
        severity=ModelSpec(kind="glm", params={"family": "gamma", "link": "log"}),
    )
    cfg = _config(tmp_path, models={"freq-sev": freq_sev})
    with pytest.raises(ValueError, match="frequency_severity"):
        tune_experiment(cfg, n_trials=1)


def test_tune_experiment_best_value_is_a_finite_inner_objective(tmp_path: Path) -> None:
    cfg = _config(tmp_path, models={"glm-tweedie": _glm()})
    result = tune_experiment(cfg, n_trials=3, calibration_penalty=1.0)
    assert np.isfinite(result.best_values["glm-tweedie"])


# ---------------------------------------------------------------------------
# Missing tune extra error path (lazy import)
# ---------------------------------------------------------------------------


def test_tune_experiment_missing_optuna_raises_helpful_error(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Force ImportError via sys.modules shim even when optuna is installed."""
    import sys

    monkeypatch.setitem(sys.modules, "optuna", None)
    cfg = _config(tmp_path, models={"glm-tweedie": _glm()})
    with pytest.raises(ImportError, match="tune"):
        tune_experiment(cfg, n_trials=1)


# ---------------------------------------------------------------------------


@pytest.mark.parametrize("custom_space", [False, True])
@pytest.mark.parametrize("split", ["random", "temporal"])
def test_tuning_does_not_inspect_outer_test_outcomes(
    monkeypatch, tmp_path: Path, custom_space: bool, split: str
) -> None:
    from azoic.models import RiskGLM

    fitted_rows = []
    actual_fit = RiskGLM.fit

    def record_fit(self, X, y):
        fitted_rows.append(X.index.copy())
        return actual_fit(self, X, y)

    monkeypatch.setattr(RiskGLM, "fit", record_fit)
    tuning = None
    if custom_space:
        tuning = {
            "search_space": {
                "glm-tweedie": {
                    "alpha": {
                        "type": "float",
                        "low": 1e-5,
                        "high": 0.1,
                        "log": True,
                    }
                }
            }
        }
    config = _config(tmp_path, models={"glm-tweedie": _glm()}, tuning=tuning)
    df = pd.read_parquet(config.data_path)
    df.index = pd.Index(np.arange(len(df)) * 7 + 10000, name="policy_id")
    df["period"] = np.arange(len(df)) % 10
    df.to_parquet(config.data_path)
    config = config.model_copy(
        update={
            "split": split,
            "spec": config.spec.model_copy(update={"time_col": "period"}),
        }
    )
    outer_train_idx, outer_test_idx = _split_indices(config, df)
    changed = df.copy()
    target_pos = changed.columns.get_loc("claim_amount")
    changed.iloc[outer_test_idx, target_pos] *= 10.0
    changed_path = tmp_path / "changed-outer.parquet"
    changed.to_parquet(changed_path)
    changed_config = config.model_copy(update={"data_path": str(changed_path)})

    original = tune_experiment(config, n_trials=3, random_state=7)
    modified = tune_experiment(changed_config, n_trials=3, random_state=7, return_estimators=True)

    assert len(fitted_rows) == 8
    for result, fit_start in [(original, 0), (modified, 4)]:
        assert result.run.train_indices == tuple(outer_train_idx)
        assert result.run.test_indices == tuple(outer_test_idx)
        expected_train = df.iloc[list(result.run.train_indices)].index
        expected_test = df.iloc[list(result.run.test_indices)].index
        pd.testing.assert_index_equal(fitted_rows[fit_start + 3], expected_train)
        for inner_rows in fitted_rows[fit_start : fit_start + 3]:
            assert len(inner_rows) < len(expected_train)
            assert set(inner_rows) < set(expected_train)
            assert not set(inner_rows) & set(expected_test)

    assert original.best_params == modified.best_params
    assert original.best_values == pytest.approx(modified.best_values, rel=1e-12)
    assert (
        original.run.models["glm-tweedie"].metrics["deviance_test"]
        != modified.run.models["glm-tweedie"].metrics["deviance_test"]
    )


def test_m7_acceptance_tuned_run_apples_to_apples(tmp_path: Path) -> None:
    config = _config(
        tmp_path,
        models={"glm-tweedie": _glm(), "gbm-tweedie": _gbm()},
        name="m7-acceptance",
    )
    result = tune_experiment(config, n_trials=3, calibration_penalty=1.0)
    baseline = run_experiment(config)

    assert set(result.best_params) == {"glm-tweedie", "gbm-tweedie"}
    assert result.n_trials == 3
    assert set(result.run.models) == set(baseline.models)
    assert result.run.feature_names == baseline.feature_names
    assert result.run.n_rows == baseline.n_rows
    assert result.run.n_train == baseline.n_train
    assert result.run.n_test == baseline.n_test
    for model_result in result.run.models.values():
        assert np.isfinite(model_result.metrics["gini_test"])
        assert np.isfinite(model_result.metrics["op_ratio_test"])
        assert np.isfinite(model_result.metrics["deviance_test"])
        assert len(model_result.calibration_table) >= 2


@pytest.mark.parametrize("return_estimators", [False, True])
def test_tuning_completes_with_claim_free_inner_and_outer_holdouts(tmp_path, return_estimators):
    config = _config(tmp_path, models={"glm-tweedie": _glm()})
    df = pd.read_parquet(config.data_path).assign(period=np.arange(2000))
    df.loc[1280:, ["claim_amount", "claim_count"]] = 0
    df.to_parquet(config.data_path)
    config = config.model_copy(
        update={"split": "temporal", "spec": config.spec.model_copy(update={"time_col": "period"})}
    )
    result = tune_experiment(config, n_trials=2, return_estimators=return_estimators)
    assert np.isfinite(result.best_values["glm-tweedie"])
    assert result.run.test_indices == tuple(range(1600, 2000))
    metrics = result.run.models["glm-tweedie"].metrics
    assert np.isnan(metrics["d2_test"])
    assert np.isfinite(metrics["deviance_test"])
    assert metrics["op_ratio_test"] == 0.0
    assert bool(result.estimators) == return_estimators


def test_tuning_trial_with_nonpositive_predictions_returns_inf_without_crashing(
    tmp_path: Path,
) -> None:
    df = pd.DataFrame(
        {
            "driver_age": [0.0, 5.0, 10.0, 15.0, 20.0, 25.0, -50.0, -60.0, -70.0, -80.0],
            "period": np.arange(10),
            "exposure": np.ones(10),
            "claim_count": [0, 1, 1, 2, 2, 3, 0, 1, 0, 1],
            "claim_amount": [0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 0.0, 10.0, 0.0, 10.0],
        }
    )
    p = tmp_path / "nonpos.parquet"
    df.to_parquet(p)
    cfg = ExperimentConfig(
        data_path=str(p),
        spec={
            "target": "claim_amount",
            "exposure": "exposure",
            "claim_count": "claim_count",
            "time_col": "period",
        },
        features=["driver_age"],
        split="temporal",
        test_size=0.2,
        models={
            "glm-normal": ModelSpec(
                kind="glm",
                params={"family": "normal", "link": "identity", "exposure_col": "exposure"},
            )
        },
        tuning={
            "n_trials": 1,
            "search_space": {"glm-normal": {"alpha": {"type": "categorical", "choices": [0.0]}}},
        },
    )
    with pytest.warns(UserWarning, match="non-positive predictions"):
        result = tune_experiment(cfg, n_trials=1)
    assert result.best_values["glm-normal"] == float("inf")
    assert result.run.models["glm-normal"].metrics["deviance_test"] == float("inf")


@pytest.mark.parametrize("preprocess", [False, True])
def test_tuning_matches_independent_studies_and_final_run(tmp_path, preprocess):
    choices = {"glm": {"alpha": [0.01, 0.1]}, "gbm": {"num_leaves": [4, 8]}}
    config = _config(
        tmp_path,
        models={"glm": _glm(), "gbm": _gbm().model_copy(update={"preprocess": False})},
        tuning={
            "search_space": {
                name: {
                    key: {"type": "categorical", "choices": values} for key, values in space.items()
                }
                for name, space in choices.items()
            }
        },
    )
    config.features = ["driver_age", "vehicle_age", "vehicle_brand"]
    config.spec = config.spec.model_copy(update={"protected_cols": ["region"]})
    if preprocess:
        config.preprocessing = PreprocessingSpec(binner={"cols": ["driver_age"], "max_bins": 3})
    df = pd.read_parquet(config.data_path)
    result = tune_experiment(config, df=df, n_trials=3, return_estimators=True)
    outer_training = df.iloc[list(result.run.train_indices)]
    for i, (name, spec) in enumerate(config.models.items()):
        study = optuna.create_study(
            direction="minimize", sampler=optuna.samplers.TPESampler(seed=42 + i)
        )

        def objective(trial, name=name, spec=spec):
            params = {
                key: trial.suggest_categorical(key, values) for key, values in choices[name].items()
            }
            trial_config = config.model_copy(
                update={
                    "models": {name: spec.model_copy(update={"params": {**spec.params, **params}})},
                    "tuning": None,
                }
            )
            inner = run_experiment(trial_config, df=outer_training)
            metrics = inner.models[name].metrics
            return metrics["deviance_test"] + abs(1 - metrics["op_ratio_test"])

        study.optimize(objective, n_trials=3)
        assert result.best_params[name] == study.best_params
        assert result.best_values[name] == pytest.approx(study.best_value)

    direct, estimators = run_experiment(result.run.config, df=df, return_estimators=True)
    assert result.run.train_indices == direct.train_indices
    assert result.run.test_indices == direct.test_indices
    assert result.run.data_fingerprint == direct.data_fingerprint
    assert result.run.feature_names == direct.feature_names
    for name in config.models:
        actual, expected = result.run.models[name], direct.models[name]
        assert actual.params == expected.params
        assert actual.metrics == pytest.approx(expected.metrics)
        pd.testing.assert_frame_equal(actual.calibration_table, expected.calibration_table)
        pd.testing.assert_frame_equal(
            actual.protected_calibration["region"], expected.protected_calibration["region"]
        )
        np.testing.assert_allclose(
            result.estimators[name].predict(df[[*config.features, config.spec.exposure]]),
            estimators[name].predict(df[[*config.features, config.spec.exposure]]),
        )
    if preprocess:
        actual = result.estimators["glm"].named_steps["binner"]
        expected = estimators["glm"].named_steps["binner"]
        for column in actual.mapping_:
            np.testing.assert_array_equal(actual.mapping_[column], expected.mapping_[column])
        assert actual.missing_ == expected.missing_
        assert actual.closure_ == expected.closure_


def test_trials_only_predict_inner_holdouts_and_build_final_results(monkeypatch, tmp_path):
    from azoic.models import RiskGLM

    predictions, runs, model_results = [], [], []
    predict, run_init, result_init = RiskGLM.predict, Run.__init__, ModelResult.__init__

    def record_predict(self, X):
        predictions.append(tuple(X.index))
        return predict(self, X)

    def record_run(self, **kwargs):
        runs.append(kwargs)
        run_init(self, **kwargs)

    def record_result(self, **kwargs):
        model_results.append(kwargs)
        result_init(self, **kwargs)

    monkeypatch.setattr(RiskGLM, "predict", record_predict)
    monkeypatch.setattr(Run, "__init__", record_run)
    monkeypatch.setattr(ModelResult, "__init__", record_result)
    config = _config(tmp_path, models={"glm": _glm()})
    df = pd.read_parquet(config.data_path)
    outer_train, outer_test = _split_indices(config, df)
    _, inner_test = _split_indices(config, df.iloc[outer_train])
    result = tune_experiment(config, df=df, n_trials=3)
    assert predictions == [tuple(df.iloc[outer_train[inner_test]].index)] * 3 + [
        tuple(df.iloc[outer_test].index),
        tuple(df.iloc[outer_train].index),
    ]
    assert len(runs) == len(model_results) == 1
    assert runs[0]["data_fingerprint"] == result.run.data_fingerprint
    assert not model_results[0]["calibration_table"].empty
    assert "gini_train" in model_results[0]["metrics"]
