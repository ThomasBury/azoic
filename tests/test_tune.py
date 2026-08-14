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
    ModelSpec,
    _split_indices,
    run_experiment,
)
from tests.conftest import make_synthetic_portfolio  # noqa: E402


def _config(
    tmp_path: Path, *, models: dict[str, ModelSpec], name: str = "smoke"
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
    result, estimators = tune_experiment(cfg, n_trials=2, return_estimators=True)
    assert isinstance(result, TuneResult)
    assert set(estimators) == {"glm-tweedie"}
    # The estimator is fitted (has coef_ from glum).
    assert hasattr(estimators["glm-tweedie"], "coef_")


def test_tune_experiment_reproducible_with_random_state(tmp_path: Path) -> None:
    cfg = _config(tmp_path, models={"glm-tweedie": _glm()})
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


def test_tuning_does_not_inspect_outer_test_outcomes(tmp_path: Path) -> None:
    config = _config(tmp_path, models={"glm-tweedie": _glm()})
    df = pd.read_parquet(config.data_path)
    _, outer_test_idx = _split_indices(config, df)
    changed = df.copy()
    target_pos = changed.columns.get_loc("claim_amount")
    changed.iloc[outer_test_idx, target_pos] *= 10.0
    changed_path = tmp_path / "changed-outer.parquet"
    changed.to_parquet(changed_path)
    changed_config = config.model_copy(update={"data_path": str(changed_path)})

    original = tune_experiment(config, n_trials=3, random_state=7)
    modified = tune_experiment(changed_config, n_trials=3, random_state=7)

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
