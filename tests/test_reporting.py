"""Tests for azoic.reporting.model_card (markdown)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from azoic.reporting import comparison_dashboard, comparison_table, model_card
from azoic.workflow import ExperimentConfig, ModelSpec, run_experiment
from tests.conftest import make_synthetic_portfolio


def _run(tmp_path: Path, *, test_rate: float | None = None):
    p = tmp_path / "portfolio.parquet"
    df = make_synthetic_portfolio(n=2000, seed=42).assign(period=np.arange(2000))
    if test_rate is not None:
        df.loc[1600:, "claim_amount"] = test_rate * df.loc[1600:, "exposure"]
        df.loc[1600:, "claim_count"] = int(test_rate > 0)
    df.to_parquet(p)
    cfg = ExperimentConfig(
        name="smoke",
        data_path=str(p),
        spec={
            "target": "claim_amount",
            "exposure": "exposure",
            "claim_count": "claim_count",
            "time_col": "period",
        },
        features=["driver_age", "vehicle_age", "region", "vehicle_brand"],
        split="random" if test_rate is None else "temporal",
        test_size=0.2,
        random_state=42,
        models={
            "glm-tweedie": ModelSpec(
                kind="glm",
                params={
                    "family": "tweedie",
                    "link": "log",
                    "exposure_col": "exposure",
                    "tweedie_power": 1.5,
                },
            ),
        },
    )
    return run_experiment(cfg)


def test_model_card_md_contains_run_and_model_summary(tmp_path: Path) -> None:
    run = _run(tmp_path)
    md = model_card(run)
    assert "Azoic model card -- smoke" in md
    assert "Model: `glm-tweedie` (glm)" in md
    assert "gini (test):" in md
    assert "O/P ratio (test):" in md
    assert run.data_fingerprint in md
    assert "Calibration table" in md
    # Calibration table preview header row + a separator row.
    assert "| group |" in md
    assert "| --- |" in md
    assert "Protected-group calibration" not in md


def test_model_card_includes_descriptive_protected_evidence(tmp_path: Path) -> None:
    path = tmp_path / "protected.parquet"
    df = make_synthetic_portfolio(n=2000, seed=43).assign(
        review_group=np.where(np.arange(2000) % 2, "review-a", "review-b")
    )
    df.to_parquet(path)
    cfg = ExperimentConfig(
        name="protected",
        data_path=str(path),
        spec={
            "target": "claim_amount",
            "exposure": "exposure",
            "claim_count": "claim_count",
            "protected_cols": ["review_group"],
        },
        features=["driver_age", "vehicle_age", "region", "vehicle_brand"],
        models={
            "glm": ModelSpec(
                kind="glm",
                params={"family": "tweedie", "link": "log", "tweedie_power": 1.5},
            )
        },
    )

    md = model_card(run_experiment(cfg))

    assert "- protected columns: `review_group`" in md
    assert "Protected-group calibration (outer test)" in md
    assert "##### `review_group`" in md
    assert "review-a" in md and "review-b" in md
    assert "descriptive only" in md
    assert "not a fairness threshold or legal assessment" in md


def test_model_card_md_includes_metrics_values(tmp_path: Path) -> None:
    run = _run(tmp_path)
    md = model_card(run)
    res = run.models["glm-tweedie"]
    # The metric values appear in the card.
    assert f"{res.metrics['gini_test']:.4f}" in md
    assert f"{res.metrics['op_ratio_test']:.4f}" in md


def test_model_card_known_layout_for_multiple_models(tmp_path: Path) -> None:
    p = tmp_path / "portfolio.parquet"
    make_synthetic_portfolio(n=2000, seed=42).to_parquet(p)
    cfg = ExperimentConfig(
        name="two",
        data_path=str(p),
        spec={"target": "claim_amount", "exposure": "exposure"},
        features=["driver_age", "vehicle_age", "region", "vehicle_brand"],
        models={
            "glm": ModelSpec(
                kind="glm", params={"family": "tweedie", "link": "log", "exposure_col": "exposure"}
            ),
            "gbm": ModelSpec(
                kind="gbm",
                params={
                    "objective": "tweedie",
                    "exposure_col": "exposure",
                    "n_estimators": 20,
                    "random_state": 42,
                },
            ),
        },
    )
    run = run_experiment(cfg)
    md = model_card(run)
    assert "Model: `glm` (glm)" in md
    assert "Model: `gbm` (gbm)" in md
    # Two model headers present.
    assert md.count("### Model:") == 2


def test_model_card_calibration_preview_is_capped(tmp_path: Path) -> None:
    run = _run(tmp_path)
    md = model_card(run)
    # The card header says it is capped to first 12 rows.
    assert "first 12 rows" in md


def test_model_card_features_line_lists_all_features(tmp_path: Path) -> None:
    run = _run(tmp_path)
    md = model_card(run)
    for c in run.feature_names:
        assert f"`{c}`" in md
    # Sanity: exact feature count is mentioned in the header.
    assert f"features ({len(run.feature_names)})" in md


def test_comparison_table_includes_all_models_and_metrics(tmp_path: Path) -> None:
    run = _run(tmp_path)
    table = comparison_table([run])

    assert list(table["model"]) == ["glm-tweedie"]
    for metric in ("gini_train", "gini_test", "op_ratio_test", "deviance_test", "d2_test"):
        assert metric in table.columns
    assert np.isfinite(table.loc[0, "d2_test"])


@pytest.mark.parametrize("test_rate", [0.0, 4.0])
def test_reporting_retains_undefined_test_d2(monkeypatch, tmp_path, test_rate) -> None:
    run = _run(tmp_path, test_rate=test_rate)
    table = comparison_table([run])
    assert np.isnan(table.loc[0, "d2_test"])
    assert np.isfinite(table.loc[0, "deviance_test"])
    assert np.isfinite(table.loc[0, "op_ratio_test"])
    card = model_card(run)
    assert next(line for line in card.splitlines() if "D² (test):" in line).endswith("nan")
    assert "Calibration table" in card

    go = pytest.importorskip("plotly.graph_objects")
    figures = []
    to_html = go.Figure.to_html

    def capture_html(figure, **kwargs):
        figures.append(json.loads(figure.to_json()))
        return to_html(figure, **kwargs)

    monkeypatch.setattr(go.Figure, "to_html", capture_html)
    html = comparison_dashboard([run])
    assert "<html>" in html and "Plotly.newPlot" in html
    metrics_table = figures[0]["data"][0]
    d2_column = metrics_table["header"]["values"].index("d2_test")
    assert metrics_table["cells"]["values"][d2_column] == [None]
