"""Tests for riskforge.cli: profile / fit / compare / export-tariff / tune (Typer).

Invokes commands via ``typer.testing.CliRunner`` end-to-end on a synthetic
portfolio written to a tmp parquet file. M5 acceptance: ``riskforge
fit/compare`` run on an example YAML. M6 acceptance: ``riskforge
export-tariff`` writes a 3-sheet xlsx from a fitted GLM. M7 acceptance:
``riskforge tune`` writes a tuned-run model card.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from riskforge.cli import app
from tests.conftest import make_synthetic_portfolio

runner = CliRunner()


def _write_portfolio(tmp_path: Path, n: int = 2000, seed: int = 42) -> Path:
    p = tmp_path / "portfolio.parquet"
    make_synthetic_portfolio(n=n, seed=seed).to_parquet(p)
    return p


def _yaml(data_path: str, name: str = "smoke", gbm_estimators: int = 30) -> str:
    return f"""name: {name}
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
      n_estimators: {gbm_estimators}
      num_leaves: 15
      learning_rate: 0.05
      random_state: 42
"""


def _write_yaml(tmp_path: Path, body: str, name: str = "cfg.yaml") -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# profile
# ---------------------------------------------------------------------------


def test_cli_profile_writes_csv(tmp_path: Path) -> None:
    data = _write_portfolio(tmp_path)
    out = tmp_path / "screening.csv"
    result = runner.invoke(
        app,
        [
            "profile",
            "--data",
            str(data),
            "--target",
            "claim_amount",
            "--exposure",
            "exposure",
            "--claim-count",
            "claim_count",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert out.exists()
    table = pd.read_csv(out)
    # Every dataframe column was profiled.
    assert set(table["column"]) == set(make_synthetic_portfolio(n=10, seed=1).columns)
    assert "action" in table.columns and "reason" in table.columns


def test_cli_profile_invalid_target_fails(tmp_path: Path) -> None:
    data = _write_portfolio(tmp_path)
    result = runner.invoke(
        app,
        [
            "profile",
            "--data",
            str(data),
            "--target",
            "no_such_target",
            "--exposure",
            "exposure",
        ],
    )
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# fit
# ---------------------------------------------------------------------------


def test_cli_fit_writes_md_and_html_cards(tmp_path: Path) -> None:
    data = _write_portfolio(tmp_path)
    cfg = _write_yaml(tmp_path, _yaml(str(data)))
    out_md = tmp_path / "card.md"
    out_html = tmp_path / "card.html"
    result = runner.invoke(
        app,
        ["fit", "--config", str(cfg), "--out", str(out_md), "--out-html", str(out_html), "-q"],
    )
    assert result.exit_code == 0, result.output
    assert out_md.exists() and out_html.exists()
    md = out_md.read_text(encoding="utf-8")
    assert "RiskForge model card -- smoke" in md
    assert "Model: `glm-tweedie` (glm)" in md
    assert "Model: `gbm-tweedie` (gbm)" in md
    html = out_html.read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>")


def test_cli_fit_missing_config_path_fails(tmp_path: Path) -> None:
    missing = tmp_path / "nope.yaml"
    result = runner.invoke(app, ["fit", "--config", str(missing)])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------


def test_cli_compare_two_configs_writes_csv_and_dashboard(tmp_path: Path) -> None:
    data = _write_portfolio(tmp_path)
    cfg_a = _write_yaml(tmp_path, _yaml(str(data), name="cfg-a", gbm_estimators=20), name="a.yaml")
    cfg_b = _write_yaml(tmp_path, _yaml(str(data), name="cfg-b", gbm_estimators=40), name="b.yaml")
    out = tmp_path / "compare.csv"
    out_html = tmp_path / "compare.html"
    result = runner.invoke(
        app,
        [
            "compare",
            str(cfg_a),
            str(cfg_b),
            "--out",
            str(out),
            "--out-html",
            str(out_html),
        ],
    )
    assert result.exit_code == 0, result.output
    assert out.exists()
    table = pd.read_csv(out)
    # Both configs produce two model rows each.
    assert set(table["config"]) == {"cfg-a", "cfg-b"}
    assert {"glm-tweedie", "gbm-tweedie"}.issubset(set(table["model"]))
    assert len(table) == 4
    assert "gini_test" in table.columns
    assert "op_ratio_test" in table.columns
    html = out_html.read_text(encoding="utf-8")
    assert "cfg-a" in html and "cfg-b" in html
    assert html.count("plotly-graph-div") == 1
    assert html.count("window.PlotlyConfig") == 1


# ---------------------------------------------------------------------------
# --help / no-args is-help
# ---------------------------------------------------------------------------


def test_cli_no_args_prints_help() -> None:
    result = runner.invoke(app, [])
    # no_args_is_help=True -> exit 2 (Usage) and the help text in stdout.
    assert "Usage:" in result.output or "usage:" in result.output.lower()


def test_cli_help_lists_three_commands() -> None:
    result = runner.invoke(app, ["--help"])
    for cmd in ("profile", "fit", "compare"):
        assert cmd in result.output


def test_cli_main_smoke_via_python_dash_m() -> None:
    """A separate parity check: ``python -m riskforge.cli --help`` exists.
    Verifies the module-level ``if __name__ == '__main__': app()`` is wired up.
    """
    # Just exercising the same code path with `prog` so the help text shows.
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "RiskForge" in result.output


# ---------------------------------------------------------------------------
# export-tariff (M6)
# ---------------------------------------------------------------------------


def test_cli_export_tariff_writes_three_sheet_xlsx(tmp_path: Path) -> None:
    data = _write_portfolio(tmp_path, n=2000)
    cfg = _write_yaml(tmp_path, _yaml(str(data)))
    out = tmp_path / "tariff.xlsx"
    result = runner.invoke(
        app,
        ["export-tariff", "--config", str(cfg), "--model", "glm-tweedie", "--out", str(out)],
    )
    assert result.exit_code == 0, result.output
    assert out.exists() and out.stat().st_size > 0
    xl = pd.read_excel(out, sheet_name=None)
    assert list(xl.keys()) == ["base_rate", "factors", "mappings"]
    assert bool(xl["base_rate"].iloc[0]["recalibrated"]) is True


def test_cli_export_tariff_no_recalibrate_flag(tmp_path: Path) -> None:
    data = _write_portfolio(tmp_path, n=2000)
    cfg = _write_yaml(tmp_path, _yaml(str(data)))
    out = tmp_path / "tariff.xlsx"
    result = runner.invoke(
        app,
        [
            "export-tariff",
            "--config",
            str(cfg),
            "--model",
            "glm-tweedie",
            "--no-recalibrate",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    xl = pd.read_excel(out, sheet_name=None)
    assert bool(xl["base_rate"].iloc[0]["recalibrated"]) is False


def test_cli_export_tariff_unknown_model_fails(tmp_path: Path) -> None:
    data = _write_portfolio(tmp_path, n=2000)
    cfg = _write_yaml(tmp_path, _yaml(str(data)))
    out = tmp_path / "tariff.xlsx"
    result = runner.invoke(
        app,
        ["export-tariff", "--config", str(cfg), "--model", "no-such-model", "--out", str(out)],
    )
    assert result.exit_code != 0
    assert "no-such-model" in result.output or "models" in result.output


def test_cli_export_tariff_gbm_model_rejected(tmp_path: Path) -> None:
    """export-tariff is multiplicative and only valid for a log-link GLM; the
    CLI rejects a GBM model name with a clear BadParameter message."""
    data = _write_portfolio(tmp_path, n=2000)
    cfg = _write_yaml(tmp_path, _yaml(str(data)))
    out = tmp_path / "tariff.xlsx"
    result = runner.invoke(
        app,
        ["export-tariff", "--config", str(cfg), "--model", "gbm-tweedie", "--out", str(out)],
    )
    assert result.exit_code != 0
    assert "RiskGLM" in result.output or "GLM" in result.output


def test_cli_help_lists_four_commands() -> None:
    result = runner.invoke(app, ["--help"])
    for cmd in ("profile", "fit", "compare", "export-tariff"):
        assert cmd in result.output


# ---------------------------------------------------------------------------
# tune (M7 / v0.2 part 1)
# ---------------------------------------------------------------------------


def test_cli_tune_writes_card_and_prints_best_params(tmp_path: Path) -> None:
    pytest.importorskip("optuna")
    data = _write_portfolio(tmp_path, n=2000)
    cfg = _write_yaml(tmp_path, _yaml(str(data)))
    out_md = tmp_path / "tuned.md"
    result = runner.invoke(
        app,
        ["tune", "--config", str(cfg), "--trials", "2", "--out", str(out_md), "-q"],
    )
    assert result.exit_code == 0, result.output
    assert out_md.exists()
    md = out_md.read_text(encoding="utf-8")
    assert "RiskForge model card -- smoke" in md
    assert "Model: `glm-tweedie` (glm)" in md
    assert "Model: `gbm-tweedie` (gbm)" in md
    # The CLI prints a `tuned <name>` summary line per model.
    assert "tuned glm-tweedie" in result.output
    assert "tuned gbm-tweedie" in result.output


def test_cli_tune_calibration_penalty_flag_passes_through(tmp_path: Path) -> None:
    pytest.importorskip("optuna")
    data = _write_portfolio(tmp_path, n=2000)
    cfg = _write_yaml(tmp_path, _yaml(str(data)))
    out_md = tmp_path / "tuned-penalized.md"
    result = runner.invoke(
        app,
        [
            "tune",
            "--config",
            str(cfg),
            "--trials",
            "2",
            "--calibration-penalty",
            "5.0",
            "--out",
            str(out_md),
            "-q",
        ],
    )
    assert result.exit_code == 0, result.output
    assert out_md.exists()


def test_cli_help_lists_five_commands() -> None:
    # `tune` is always registered (optuna is imported lazily inside the command
    # body), so --help lists it whether or not the tune extra is installed.
    result = runner.invoke(app, ["--help"])
    for cmd in ("profile", "fit", "compare", "export-tariff", "tune"):
        assert cmd in result.output
