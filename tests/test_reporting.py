"""Tests for riskforge.reporting.model_card (markdown and HTML)."""

from __future__ import annotations

from pathlib import Path

import pytest

from riskforge.reporting import (
    comparison_dashboard,
    comparison_table,
    model_card,
)
from riskforge.workflow import ExperimentConfig, ModelSpec, run_experiment
from tests.conftest import make_synthetic_portfolio


def _run(tmp_path: Path):
    p = tmp_path / "portfolio.parquet"
    make_synthetic_portfolio(n=2000, seed=42).to_parquet(p)
    cfg = ExperimentConfig(
        name="smoke",
        data_path=str(p),
        spec={"target": "claim_amount", "exposure": "exposure", "claim_count": "claim_count"},
        features=["driver_age", "vehicle_age", "region", "vehicle_brand"],
        split="random",
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
    md = model_card(run, fmt="md")
    assert "RiskForge model card -- smoke" in md
    assert "Model: `glm-tweedie` (glm)" in md
    assert "gini (test):" in md
    assert "O/P ratio (test):" in md
    assert run.data_fingerprint in md
    assert "Calibration table" in md
    # Calibration table preview header row + a separator row.
    assert "| group |" in md
    assert "| --- |" in md


def test_model_card_html_escapes_markdown(tmp_path: Path) -> None:
    run = _run(tmp_path)
    html = model_card(run, fmt="html")
    assert html.startswith("<!doctype html>")
    assert "<pre>" in html and "</pre>" in html
    # The markdown body must be HTML-escaped inside <pre>.
    assert "RiskForge model card -- smoke" in html
    assert "|" in html  # calibration table survives escaping


def test_model_card_md_includes_metrics_values(tmp_path: Path) -> None:
    run = _run(tmp_path)
    md = model_card(run, fmt="md")
    res = run["glm-tweedie"]
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
            "glm": ModelSpec(kind="glm",
                             params={"family": "tweedie", "link": "log",
                                     "exposure_col": "exposure"}),
            "gbm": ModelSpec(kind="gbm", params={"objective": "tweedie",
                                                 "exposure_col": "exposure",
                                                 "n_estimators": 20, "random_state": 42}),
        },
    )
    run = run_experiment(cfg)
    md = model_card(run, fmt="md")
    assert "Model: `glm` (glm)" in md
    assert "Model: `gbm` (gbm)" in md
    # Two model headers present.
    assert md.count("### Model:") == 2


def test_model_card_unknown_fmt_raises(tmp_path: Path) -> None:
    run = _run(tmp_path)
    with pytest.raises(ValueError, match="fmt"):
        model_card(run, fmt="pdf")  # type: ignore[arg-type]


def test_model_card_calibration_preview_is_capped(tmp_path: Path) -> None:
    run = _run(tmp_path)
    md = model_card(run, fmt="md")
    # The card header says it is capped to first 12 rows.
    assert "first 12 rows" in md


def test_model_card_features_line_lists_all_features(tmp_path: Path) -> None:
    run = _run(tmp_path)
    md = model_card(run, fmt="md")
    for c in run.feature_names:
        assert f"`{c}`" in md
    # Sanity: exact feature count is mentioned in the header.
    assert f"features ({len(run.feature_names)})" in md


def test_comparison_table_and_dashboard_include_all_models_and_metrics(tmp_path: Path) -> None:
    run = _run(tmp_path)
    table = comparison_table([run])

    assert list(table["model"]) == ["glm-tweedie"]
    for metric in ("gini_train", "gini_test", "op_ratio_test", "deviance_test"):
        assert metric in table.columns

    html = comparison_dashboard([run])
    assert "glm-tweedie" in html
    assert html.count("plotly-graph-div") == 1
    assert html.count("window.PlotlyConfig") == 1
    assert 'src="https://cdn.plot.ly' not in html
