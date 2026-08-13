"""Tests for riskforge.mlops.log_run (thin lazy mlflow shim, M6).

mlflow is provided by the ``mlops`` extra. These tests point mlflow at a
sqlite tracking db under ``tmp_path`` so no real mlflow server is needed
(file-store backend is in maintenance mode in mlflow 3.x). The acceptance
test asserts a logged run records top-level params, per-model params +
metrics, and an artifact file.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

mlflow = pytest.importorskip("mlflow")  # skip the whole module if mlops extra absent

from riskforge.mlops import MissingMLOpsExtra, log_run  # noqa: E402
from riskforge.workflow import ExperimentConfig, ModelSpec, run_experiment  # noqa: E402
from tests.conftest import make_synthetic_portfolio  # noqa: E402


def _run(tmp_path: Path, *, models: dict[str, ModelSpec] | None = None) -> tuple:
    p = tmp_path / "portfolio.parquet"
    make_synthetic_portfolio(n=2000, seed=42).to_parquet(p)
    if models is None:
        models = {
            "glm-tweedie": ModelSpec(
                kind="glm",
                params={
                    "family": "tweedie", "link": "log", "exposure_col": "exposure",
                    "tweedie_power": 1.5,
                },
            ),
            "gbm-tweedie": ModelSpec(
                kind="gbm",
                params={
                    "objective": "tweedie", "exposure_col": "exposure",
                    "tweedie_variance_power": 1.5, "n_estimators": 20,
                    "num_leaves": 15, "random_state": 42,
                },
            ),
        }
    cfg = ExperimentConfig(
        name="smoke",
        data_path=str(p),
        spec={"target": "claim_amount", "exposure": "exposure", "claim_count": "claim_count"},
        features=["driver_age", "vehicle_age", "region", "vehicle_brand"],
        split="random",
        test_size=0.2,
        random_state=42,
        models=models,
    )
    return cfg, run_experiment(cfg)


def _tracking_uri(tmp_path: Path) -> str:
    # sqlite backend -- the file store is in maintenance mode in mlflow 3.x.
    return f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}"


def _data(run_id: str):
    return mlflow.get_run(run_id).data


def _list_artifacts(run_id: str, path: str | None = None):
    client = mlflow.tracking.MlflowClient()
    return client.list_artifacts(run_id, path=path) if path else client.list_artifacts(run_id)


# ---------------------------------------------------------------------------
# log_run -- happy path
# ---------------------------------------------------------------------------


def test_log_run_returns_run_id_and_records_experiment_params(tmp_path: Path) -> None:
    cfg, run = _run(tmp_path)
    uri = _tracking_uri(tmp_path)
    run_id = log_run(run, tracking_uri=uri, experiment_name="riskforge-tests")
    assert isinstance(run_id, str) and len(run_id) > 0

    mlflow.set_tracking_uri(uri)
    exp = mlflow.get_experiment_by_name("riskforge-tests")
    assert exp is not None
    data = _data(run_id)
    assert data.params["experiment.name"] == "smoke"
    assert data.params["experiment.split"] == "random"
    assert int(data.params["experiment.n_rows"]) == run.n_rows
    assert int(data.params["experiment.n_train"]) == run.n_train
    assert int(data.params["experiment.n_test"]) == run.n_test
    assert data.params["experiment.data_fingerprint"] == run.data_fingerprint
    assert "experiment.feature_names" in data.params


def test_log_run_records_per_model_params_and_metrics(tmp_path: Path) -> None:
    cfg, run = _run(tmp_path)
    uri = _tracking_uri(tmp_path)
    run_id = log_run(run, tracking_uri=uri, experiment_name="riskforge-tests")
    data = _data(run_id)

    for name in run.models:
        assert data.params[f"{name}.kind"] == run[name].kind
        # GLM/GBM constructor params round-trip as strings.
        for k, v in run[name].params.items():
            assert f"{name}.params.{k}" in data.params
            assert data.params[f"{name}.params.{k}"] == str(v)
        # Every finite metric is logged with the <model>.<metric> key.
        for k, v in run[name].metrics.items():
            fv = float(v)
            if fv == fv and fv not in (float("inf"), float("-inf")):
                assert f"{name}.{k}" in data.metrics


def test_log_run_logs_artifact_files(tmp_path: Path) -> None:
    cfg, run = _run(tmp_path)
    uri = _tracking_uri(tmp_path)
    art_dir = tmp_path / "arts"
    art_dir.mkdir()
    f1 = art_dir / "note.txt"
    f1.write_text("hello", encoding="utf-8")
    f2 = art_dir / "card.md"
    f2.write_text("# card", encoding="utf-8")

    run_id = log_run(
        run, tracking_uri=uri, experiment_name="riskforge-tests",
        artifacts=[f1, f2],
    )

    arts = _list_artifacts(run_id, path="artifacts")
    names = {a.path.split("/")[-1] for a in arts}
    assert "note.txt" in names and "card.md" in names


def test_log_run_logs_artifact_directory(tmp_path: Path) -> None:
    cfg, run = _run(tmp_path)
    uri = _tracking_uri(tmp_path)
    art_dir = tmp_path / "artdir"
    art_dir.mkdir()
    (art_dir / "a.txt").write_text("a", encoding="utf-8")
    (art_dir / "b.txt").write_text("b", encoding="utf-8")

    run_id = log_run(
        run, tracking_uri=uri, experiment_name="riskforge-tests",
        artifacts=[art_dir],
    )

    arts = _list_artifacts(run_id, path="artifacts/artdir")
    names = {a.path.split("/")[-1] for a in arts}
    assert {"a.txt", "b.txt"}.issubset(names)


def test_log_run_missing_artifact_raises(tmp_path: Path) -> None:
    cfg, run = _run(tmp_path)
    uri = _tracking_uri(tmp_path)
    with pytest.raises(FileNotFoundError, match="artifact not found"):
        log_run(
            run, tracking_uri=uri, experiment_name="riskforge-tests",
            artifacts=[tmp_path / "nope.txt"],
        )


def test_log_run_run_name_overrides_default(tmp_path: Path) -> None:
    cfg, run = _run(tmp_path, models={
        "glm": ModelSpec(kind="glm", params={"family": "tweedie", "link": "log",
                                             "exposure_col": "exposure"}),
    })
    uri = _tracking_uri(tmp_path)
    run_id = log_run(
        run, tracking_uri=uri, experiment_name="riskforge-tests",
        run_name="custom-name",
    )
    info = mlflow.get_run(run_id).info
    assert info.run_name == "custom-name"


def test_log_run_skips_nonfinite_metrics(tmp_path: Path) -> None:
    """A NaN metric (e.g. op_ratio when pred_total==0) should be silently
    dropped, not logged (mlflow 3.x rejects NaN)."""
    cfg, run = _run(tmp_path)
    # Inject a NaN metric on one model.
    res = run.models["glm-tweedie"]
    bad = res.model_copy(update={"metrics": {"foo_nan": float("nan"), **res.metrics}})
    run = run.model_copy(update={"models": {**run.models, "glm-tweedie": bad}})

    uri = _tracking_uri(tmp_path)
    run_id = log_run(run, tracking_uri=uri, experiment_name="riskforge-tests")
    data = _data(run_id)
    assert "glm-tweedie.foo_nan" not in data.metrics
    # the finite metrics still went through.
    assert "glm-tweedie.gini_test" in data.metrics


# ---------------------------------------------------------------------------
# MissingMLOpsExtra error path (lazy import)
# ---------------------------------------------------------------------------


def test_log_run_missing_mlflow_raises_helpful_error(monkeypatch, tmp_path: Path) -> None:
    """If mlflow is uninstallable, log_run raises MissingMLOpsExtra with the
    ``mlops`` extra pointer. We force ImportError via sys.modules shim even
    when mlflow is installed so the test runs in the dev env."""
    import sys

    monkeypatch.setitem(sys.modules, "mlflow", None)
    cfg, run = _run(tmp_path)
    with pytest.raises(MissingMLOpsExtra, match="mlops"):
        log_run(run, tracking_uri=_tracking_uri(tmp_path))


# ---------------------------------------------------------------------------
# M6 acceptance: a logged run records params / metrics / artifacts together
# ---------------------------------------------------------------------------


def test_m6_acceptance_mlflow_run_records_params_metrics_artifacts(tmp_path: Path) -> None:
    cfg, run = _run(tmp_path, models={
        "glm-tweedie": ModelSpec(
            kind="glm",
            params={"family": "tweedie", "link": "log", "exposure_col": "exposure",
                    "tweedie_power": 1.5},
        ),
    })
    # Persist the model card as the artifact.
    from riskforge.reporting import model_card

    card_path = tmp_path / "card.md"
    card_path.write_text(model_card(run, fmt="md"), encoding="utf-8")

    uri = _tracking_uri(tmp_path)
    run_id = log_run(
        run, tracking_uri=uri, experiment_name="riskforge-m6-acceptance",
        artifacts=[card_path],
    )
    mlflow.set_tracking_uri(uri)
    data = _data(run_id)

    # 1. Parameters: experiment fingerprint + per-model params.
    assert data.params["experiment.name"] == cfg.name
    assert data.params["glm-tweedie.kind"] == "glm"
    assert data.params["glm-tweedie.params.family"] == "tweedie"

    # 2. Metrics: finite per-model metrics logged.
    assert "glm-tweedie.gini_test" in data.metrics
    assert "glm-tweedie.op_ratio_test" in data.metrics
    assert np.isfinite(float(data.metrics["glm-tweedie.gini_test"]))

    # 3. Artifact: the model card landed under artifacts/.
    arts = _list_artifacts(run_id, path="artifacts")
    assert any(a.path.endswith("card.md") for a in arts)
