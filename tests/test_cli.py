"""Tests for azoic.cli: profile / fit / compare / export-tariff / tune (Typer).

Invokes commands via ``typer.testing.CliRunner`` end-to-end on a synthetic
portfolio written to a tmp parquet file. M5 acceptance: ``azoic
fit/compare`` run on an example YAML. M6 acceptance: ``azoic
export-tariff`` writes a 3-sheet xlsx from a fitted GLM. M7 acceptance:
``azoic tune`` writes a tuned-run model card.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from azoic.cli import app
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


def test_cli_profile_prints_plain_table_to_stdout(tmp_path: Path) -> None:
    data = _write_portfolio(tmp_path, n=100)
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
        ],
    )
    assert result.exit_code == 0, result.output
    assert "column" in result.output
    assert "claim_amount" in result.output
    assert "action" in result.output


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


@pytest.mark.parametrize(
    "path", ["s3://bucket/prefix/portfolio.parquet", "./local/portfolio.parquet"]
)
def test_cli_profile_forwards_exact_path(monkeypatch, path) -> None:
    received = []

    def loader(data, spec):
        received.append((data, spec))
        return pd.DataFrame({"amount": [0.0, 1.0], "exposure": [1.0, 1.0]})

    monkeypatch.setattr("azoic.cli.load_data", loader)
    result = runner.invoke(
        app, ["profile", "--data", path, "--target", "amount", "--exposure", "exposure"]
    )
    assert result.exit_code == 0, result.exception
    assert received[0][0] == path
    assert received[0][1].target == "amount"


# ---------------------------------------------------------------------------
# fit
# ---------------------------------------------------------------------------


def test_cli_fit_writes_md_card(tmp_path: Path) -> None:
    data = _write_portfolio(tmp_path)
    cfg = _write_yaml(tmp_path, _yaml(str(data)))
    out_md = tmp_path / "card.md"
    result = runner.invoke(
        app,
        ["fit", "--config", str(cfg), "--out", str(out_md), "-q"],
    )
    assert result.exit_code == 0, result.output
    assert out_md.exists()
    md = out_md.read_text(encoding="utf-8")
    assert "Azoic model card -- smoke" in md
    assert "Model: `glm-tweedie` (glm)" in md
    assert "Model: `gbm-tweedie` (gbm)" in md


def test_cli_fit_shipped_yaml_from_another_directory(tmp_path: Path, monkeypatch) -> None:
    source = Path(__file__).parents[1] / "examples" / "tweedie.yaml"
    config_dir = tmp_path / "example"
    config_dir.mkdir()
    config = config_dir / source.name
    config.write_bytes(source.read_bytes())
    make_synthetic_portfolio(n=2000).to_parquet(config_dir / "synthetic.parquet")
    monkeypatch.chdir(tmp_path)
    card = tmp_path / "card.md"

    result = runner.invoke(app, ["fit", "--config", str(config), "--out", str(card), "-q"])

    assert result.exit_code == 0, result.output
    content = card.read_text()
    assert "Model: `tweedie-glm` (glm)" in content
    assert "Model: `tweedie-gbm` (gbm)" in content


def test_cli_fit_missing_config_path_fails(tmp_path: Path) -> None:
    missing = tmp_path / "nope.yaml"
    result = runner.invoke(app, ["fit", "--config", str(missing)])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------


def test_cli_compare_two_configs_writes_csv(tmp_path: Path) -> None:
    data = _write_portfolio(tmp_path)
    cfg_a = _write_yaml(tmp_path, _yaml(str(data), name="cfg-a", gbm_estimators=20), name="a.yaml")
    cfg_b = _write_yaml(tmp_path, _yaml(str(data), name="cfg-b", gbm_estimators=40), name="b.yaml")
    out = tmp_path / "compare.csv"
    result = runner.invoke(
        app,
        ["compare", str(cfg_a), str(cfg_b), "--out", str(out)],
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


@pytest.mark.parametrize("distill", [False, True])
@pytest.mark.parametrize("changed_data", [False, True])
def test_cli_export_tariff_uses_stored_split_and_rejects_changed_data(
    monkeypatch, tmp_path: Path, changed_data: bool, distill: bool
) -> None:
    import azoic.cli as cli

    actual_run = cli.run_experiment
    actual_distill = cli._distill_gbm
    runs = []
    partitions = []

    def record_run(config, **kwargs):
        run, estimators = actual_run(config.model_copy(update={"random_state": 7}), **kwargs)
        runs.append(run)
        if changed_data:
            frame = pd.read_parquet(config.data_path)
            frame.iloc[::-1].to_parquet(config.data_path)
        return run, estimators

    def record_distill(teacher, X_fit, X_valid):
        partitions.append((X_fit.copy(), X_valid.copy()))
        return actual_distill(teacher, X_fit, X_valid)

    monkeypatch.setattr(cli, "run_experiment", record_run)
    monkeypatch.setattr(cli, "_distill_gbm", record_distill)
    data = _write_portfolio(tmp_path, n=2000)
    cfg = _write_yaml(tmp_path, _yaml(str(data)))
    out = tmp_path / "distilled.xlsx"
    result = runner.invoke(
        app,
        [
            "export-tariff",
            "--config",
            str(cfg),
            "--model",
            "gbm-tweedie" if distill else "glm-tweedie",
            *(["--distill"] if distill else []),
            "--no-recalibrate",
            "--out",
            str(out),
        ],
    )

    if changed_data:
        assert result.exit_code != 0
        assert "changed since fitting" in result.output
        assert not partitions
        assert not out.exists()
        return

    assert result.exit_code == 0, result.output
    if not distill:
        assert not partitions
        assert out.exists()
        return
    assert "Distillation fidelity" in result.output
    run = runs[0]
    frame = pd.read_parquet(data)
    assert len(partitions) == 1
    fit, valid = partitions[0]
    pd.testing.assert_frame_equal(fit, frame.iloc[list(run.train_indices)][fit.columns])
    pd.testing.assert_frame_equal(valid, frame.iloc[list(run.test_indices)][valid.columns])
    sheets = pd.read_excel(out, sheet_name=None)
    assert list(sheets) == ["base_rate", "factors", "mappings"]
    base = sheets["base_rate"].iloc[0]
    assert base["distilled_from"] == "RiskGBM"
    assert base["teacher_objective"] == "tweedie"
    assert float(base["teacher_student_deviance"]) >= 0
    assert float(base["student_teacher_total_ratio"]) == pytest.approx(1.0, rel=0.05)


@pytest.mark.parametrize("distill", [False, True])
@pytest.mark.parametrize("recalibrate", [False, True])
def test_cli_export_tariff_ignores_holdout_outcomes(
    monkeypatch, tmp_path: Path, distill: bool, recalibrate: bool
) -> None:
    import azoic.cli as cli
    from azoic.tariff import apply_tariff, extract_tariff

    frame = make_synthetic_portfolio(n=1000)
    frame.index = np.arange(len(frame)) * 3 + 17
    data = tmp_path / "portfolio.parquet"
    frame.to_parquet(data)
    cfg = _write_yaml(
        tmp_path,
        _yaml(str(data))
        + "preprocessing:\n  binner:\n    cols: [driver_age, vehicle_age]\n    max_bins: 4\n",
    )
    actual_run = cli.run_experiment
    actual_export = cli._export_tariff
    runs = []
    exports = []

    def record_run(config, **kwargs):
        run, estimators = actual_run(config.model_copy(update={"random_state": 7}), **kwargs)
        runs.append(run)
        return run, estimators

    def record_export(est, out, **kwargs):
        exports.append((est, kwargs["X"].copy(), kwargs["y"].copy()))
        return actual_export(est, out, **kwargs)

    monkeypatch.setattr(cli, "run_experiment", record_run)
    monkeypatch.setattr(cli, "_export_tariff", record_export)
    workbooks = []
    for attempt in range(2):
        out = tmp_path / f"tariff-{attempt}.xlsx"
        result = runner.invoke(
            app,
            [
                "export-tariff",
                "--config",
                str(cfg),
                "--model",
                "gbm-tweedie" if distill else "glm-tweedie",
                *(["--distill"] if distill else []),
                *([] if recalibrate else ["--no-recalibrate"]),
                "--out",
                str(out),
            ],
        )
        assert result.exit_code == 0, result.output
        workbooks.append(pd.read_excel(out, sheet_name=None))
        if attempt == 0:
            changed = frame.copy()
            target_col = changed.columns.get_loc("claim_amount")
            changed.iloc[list(runs[0].test_indices), target_col] *= 10
            changed.to_parquet(data)

    assert runs[0].train_indices == runs[1].train_indices
    assert runs[0].test_indices == runs[1].test_indices
    assert set(runs[0].train_indices).isdisjoint(runs[0].test_indices)
    assert runs[0].data_fingerprint != runs[1].data_fingerprint
    est, calibration_X, calibration_y = exports[0]
    X = frame[list(est.feature_names_in_)]
    np.testing.assert_allclose(est.predict(X), exports[1][0].predict(X))
    for sheet in workbooks[0]:
        pd.testing.assert_frame_equal(workbooks[0][sheet], workbooks[1][sheet])

    train = frame.iloc[list(runs[0].train_indices)]
    glm = est.steps[-1][1]
    tariff = extract_tariff(glm)
    structural_base = tariff["base_rate"]
    base = float(workbooks[0]["base_rate"].iloc[0]["base_rate"])
    factor = train["claim_amount"].sum() / np.dot(
        est.predict(X.iloc[list(runs[0].train_indices)]), train["exposure"]
    )
    assert base / structural_base == pytest.approx(factor if recalibrate else 1.0)
    if recalibrate:
        pd.testing.assert_frame_equal(calibration_X, X.iloc[list(runs[0].train_indices)])
        pd.testing.assert_series_equal(calibration_y, train["claim_amount"])

    tariff["base_rate"] = base
    for row in workbooks[0]["factors"].itertuples(index=False):
        if row.level == "_per_unit":
            tariff["numeric"][row.feature] = np.log(row.multiplicative_factor)
        else:
            tariff["categorical"][row.feature][row.level] = row.multiplicative_factor
    workbook_rates = apply_tariff(tariff, est[:-1].transform(X))
    np.testing.assert_allclose(workbook_rates, est.predict(X) * (factor if recalibrate else 1.0))
    if recalibrate:
        assert np.dot(
            workbook_rates[list(runs[0].train_indices)], train["exposure"]
        ) == pytest.approx(train["claim_amount"].sum())


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
    assert "Azoic model card -- smoke" in md
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


def test_cli_tune_options_defer_to_yaml_and_override_when_supplied(
    monkeypatch, tmp_path: Path
) -> None:
    import azoic.tune as tune_module

    calls = []

    def capture(config, *, n_trials=None, calibration_penalty=None):
        calls.append((n_trials, calibration_penalty, config.tuning))
        return SimpleNamespace(run=object(), best_params={})

    monkeypatch.setattr(tune_module, "tune_experiment", capture)
    monkeypatch.setattr("azoic.cli.model_card", lambda run: "")
    configured = _write_yaml(
        tmp_path,
        _yaml("ignored")
        + """tuning:
  n_trials: 3
  calibration_penalty: 2.0
""",
        name="configured.yaml",
    )
    fallback = _write_yaml(tmp_path, _yaml("ignored"), name="fallback.yaml")

    omitted = runner.invoke(app, ["tune", "--config", str(configured), "--quiet"])
    explicit = runner.invoke(
        app,
        [
            "tune",
            "--config",
            str(configured),
            "--trials",
            "4",
            "--calibration-penalty",
            "5.0",
            "--quiet",
        ],
    )
    legacy = runner.invoke(app, ["tune", "--config", str(fallback), "--quiet"])

    assert omitted.exit_code == explicit.exit_code == legacy.exit_code == 0
    assert calls[0][0:2] == (None, None)
    assert calls[0][2].n_trials == 3
    assert calls[0][2].calibration_penalty == 2.0
    assert calls[1][0:2] == (4, 5.0)
    assert calls[2] == (None, None, None)


def test_cli_help_lists_five_commands() -> None:
    # `tune` is always registered (optuna is imported lazily inside the command
    # body), so --help lists it whether or not the tune extra is installed.
    result = runner.invoke(app, ["--help"])
    for cmd in ("profile", "fit", "compare", "export-tariff", "tune"):
        assert cmd in result.output
