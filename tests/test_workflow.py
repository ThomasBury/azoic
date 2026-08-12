"""Tests for riskforge.workflow: ExperimentConfig, run_experiment, Run."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from riskforge.workflow import (
    ExperimentConfig,
    ModelResult,
    ModelSpec,
    Run,
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
    from riskforge.models import RiskGBM, RiskGLM

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


def test_experiment_config_rejects_extra_fields(tmp_path: Path) -> None:
    body = _basic_yaml("ignored") + "extra_field: 1\n"
    yaml_path = _write_yaml(tmp_path, body)
    with pytest.raises(Exception, match="extra"):
        ExperimentConfig.from_yaml(yaml_path)


def test_experiment_config_features_default_is_all_non_special(tmp_path: Path) -> None:
    df = make_synthetic_portfolio(n=20, seed=1)
    cfg = ExperimentConfig(
        name="x",
        data_path="ignored",
        spec={"target": "claim_amount", "exposure": "exposure", "claim_count": "claim_count"},
        models={"glm-tweedie": ModelSpec(kind="glm", params={"family": "tweedie"})},
    )
    feats = cfg.feature_columns(df)
    assert set(feats) == {"driver_age", "vehicle_age", "region", "vehicle_brand"}


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
    # __getitem__ access.
    assert run["glm-tweedie"].name == "glm-tweedie"


def test_run_experiment_returns_estimators_when_requested(tmp_path: Path) -> None:
    data = _write_portfolio(tmp_path, n=2000)
    yaml_path = _write_yaml(tmp_path, _basic_yaml(str(data)))
    cfg = ExperimentConfig.from_yaml(yaml_path)
    run, ests = run_experiment(cfg, return_estimators=True)
    assert set(ests.keys()) == {"glm-tweedie", "gbm-tweedie"}
    assert hasattr(ests["glm-tweedie"], "predict")
    assert hasattr(ests["gbm-tweedie"], "predict")


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
    body = (
        f"""name: smoke
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
    )
    yaml_path = _write_yaml(tmp_path, body)
    cfg = ExperimentConfig.from_yaml(yaml_path)
    run = run_experiment(cfg)
    assert run.n_test == int(round(2000 * 0.2))
    assert run.n_train == 2000 - run.n_test
    assert run.models["glm-tweedie"].metrics["gini_test"] >= 0.0


def test_run_experiment_pure_premium_op_ratio_near_one(tmp_path: Path) -> None:
    """In-sample adequacy: op_ratio on test should be close to 1.0 for a Tweedie
    GLM with exposure as weight (no exposure leakage, weight convention ok)."""
    data = _write_portfolio(tmp_path)
    yaml_path = _write_yaml(tmp_path, _basic_yaml(str(data)))
    cfg = ExperimentConfig.from_yaml(yaml_path)
    run = run_experiment(cfg)
    op = run["glm-tweedie"].metrics["op_ratio_test"]
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
# M5 acceptance: end-to-end on synthetic data
# ---------------------------------------------------------------------------


def test_m5_acceptance_example_config_runs_end_to_end(tmp_path: Path) -> None:
    """M5 done-when: an example YAML config runs end-to-end on the synthetic
    portfolio -- both models fit, predict, score, and the model card / Run are
    populated."""
    data = _write_portfolio(tmp_path, n=4000)
    yaml_path = _write_yaml(tmp_path, _basic_yaml(str(data)))
    cfg = ExperimentConfig.from_yaml(yaml_path)
    run = run_experiment(cfg)

    # Both estimators produce a non-trivial ranking on the test set.
    for name in run.models:
        assert run[name].metrics["gini_test"] > 0.0, f"{name} gini_test not positive"
        op = run[name].metrics["op_ratio_test"]
        assert 0.5 <= op <= 1.5, f"{name} op_ratio_test drift: {op:.3f}"
        # Calibration table is non-empty and has all expected columns.
        tbl = run[name].calibration_table
        assert len(tbl) >= 2
        assert {"exposure", "claim_amount", "observed_pure_premium",
                "predicted_pure_premium", "o_p_ratio"}.issubset(tbl.columns)
