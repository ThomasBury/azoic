"""Chapter assembly checks with synthetic data and no pre-existing reports."""

import ast
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from tests.conftest import make_synthetic_portfolio


def _portfolio_loader(artifact_dir, fetch):
    shared = (Path(__file__).parents[1] / "examples" / "_shared.qmd").read_text()
    cell = next(
        cell
        for cell in re.findall(r"```\{python\}\n(.*?)\n```", shared, flags=re.DOTALL)
        if "def load_portfolio():" in cell
    )
    namespace = {
        "pd": pd,
        "fetch_openml": fetch,
        "ARTIFACT_DIR": artifact_dir,
        "JOINED_PATH": artifact_dir / "fremtpl2_joined_v3.parquet",
        "PORTFOLIO_PATH": artifact_dir / "portfolio_v3.parquet",
        "AUDIT_PATH": artifact_dir / "cleaning_audit_v1.csv",
        "CLAIM_CAP": 100_000.0,
        "SAMPLE_SIZE": 1_000_000,
        "RANDOM_STATE": 42,
    }
    exec(cell, namespace)
    return namespace


def test_portfolio_audit_reconciles_first_failures_and_cache_rebuilds(tmp_path):
    frequency = pd.DataFrame(
        {
            "IDpol": [8, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, np.nan],
            "Exposure": [0.5, 1, 0, 1, 1, 1, 1, 1, 1, 1, 1, np.nan, 1],
            "ClaimNb": [2, 0, 1, -1, 1, 1, 1, 1, 1, 1, 0, 1, 1],
            "DrivAge": [40, 18, 17, 40, 40, 17, 40, 40, 40, 40, 40, 40, 40],
            "VehAge": [0, 100, 0, 0, 0, 0, 101, 0, 0, 0, 0, 0, 0],
            "BonusMalus": [50, 230, 50, 50, 50, 50, 50, 231, 50, 50, 50, 50, 50],
            "VehPower": [2, 15, 2, 2, 2, 2, 2, 2, 16, 2, 2, 2, 2],
            "Density": [1, 1, 0, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1],
            "Region": [None] + ["R1"] * 12,
            "VehBrand": ["B1"] * 13,
            "VehGas": ["Diesel"] * 13,
            "Area": ["A"] * 13,
        }
    )
    severity = pd.DataFrame(
        {
            "IDpol": [8, 8, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 99],
            "ClaimAmount": [120, 70, 10, 10, -5, 10, 10, 10, 10, 10, 5, 10, 500],
        }
    )
    calls = []

    def fetch(*, data_id, **kwargs):
        calls.append(data_id)
        return SimpleNamespace(frame={41214: frequency, 41215: severity}[data_id])

    namespace = _portfolio_loader(tmp_path, fetch)
    namespace["CLAIM_CAP"] = 100.0
    load = namespace["load_portfolio"]
    result = load()
    cleaned = pd.read_parquet(namespace["JOINED_PATH"])
    audit = pd.read_csv(namespace["AUDIT_PATH"])
    assert calls == [41214, 41215]
    assert result["policy_id"].tolist() == [2.0, 8.0]
    assert cleaned["policy_id"].tolist() == [8.0, 2.0]
    assert result["claim_amount"].tolist() == [0.0, 170.0]
    assert result["veh_power"].tolist() == ["15", "2"]
    assert result["region"].tolist() == ["R1", "Missing"]
    assert cleaned.dtypes.astype(str).tolist() == [
        "float64",
        "float64",
        "int64",
        "float64",
        "int64",
        "int64",
        "int64",
        "int64",
        str(pd.Series(["value"]).astype(str).dtype),
        str(pd.Series(["value"]).astype(str).dtype),
        str(pd.Series(["value"]).astype(str).dtype),
        str(pd.Series(["value"]).astype(str).dtype),
        str(pd.Series(["value"]).astype(str).dtype),
    ]
    assert audit["removed_policies"].tolist() == [0, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1]
    assert audit.iloc[0]["raw_severity_claim_amount"] == 770
    assert audit.iloc[0]["capped_severity_claim_amount"] == 350
    assert audit.iloc[0]["retained_claim_amount"] == 250
    assert audit.iloc[0]["claim_cap"] == 100
    for metric in ["policies", "exposure", "claim_count", "claim_amount"]:
        np.testing.assert_allclose(
            audit[f"retained_{metric}"].iloc[:-1],
            audit[f"removed_{metric}"].iloc[1:] + audit[f"retained_{metric}"].iloc[1:],
        )
        expected = len(result) if metric == "policies" else result[metric].sum()
        assert audit.iloc[-1][f"retained_{metric}"] == expected
    overlap = audit.set_index("rule").loc["Exposure outside (0, 1]"]
    assert overlap["removed_claim_count"] == 2
    assert overlap["removed_claim_amount"] == 20
    pd.testing.assert_frame_equal(load(), result)
    pd.testing.assert_frame_equal(pd.read_csv(namespace["AUDIT_PATH"]), audit)
    assert calls == [41214, 41215]
    namespace["SAMPLE_SIZE"] = 1
    assert len(load()) == 1
    pd.testing.assert_frame_equal(pd.read_csv(namespace["AUDIT_PATH"]), audit)
    namespace["SAMPLE_SIZE"] = 1_000_000
    for missing in ["AUDIT_PATH", "JOINED_PATH"]:
        namespace[missing].unlink()
        pd.testing.assert_frame_equal(load(), result)
        pd.testing.assert_frame_equal(pd.read_csv(namespace["AUDIT_PATH"]), audit)
        pd.testing.assert_frame_equal(pd.read_parquet(namespace["JOINED_PATH"]), cleaned)
    assert calls == [41214, 41215] * 3


@pytest.mark.parametrize(
    "chapter_name",
    [
        "02-experiments.qmd",
        "04-scoring-tariff.qmd",
        "05-reporting-mlops.qmd",
        "06-frequency-severity.qmd",
        "07-tuning.qmd",
    ],
)
def test_chapter_builds_its_own_artifacts_in_fresh_process(tmp_path, chapter_name):
    if chapter_name not in {"06-frequency-severity.qmd", "07-tuning.qmd"}:
        pytest.importorskip("mlflow")
        pytest.importorskip("plotly")
    if chapter_name == "07-tuning.qmd":
        pytest.importorskip("optuna")
    pytest.importorskip("IPython")
    examples = Path(__file__).parents[1] / "examples"
    chapter = (examples / chapter_name).read_text()
    chapter = chapter.split("## Drive the same workflow from the CLI")[0]
    chapter = chapter.replace("{{< include _shared.qmd >}}", (examples / "_shared.qmd").read_text())
    cells = re.findall(r"```\{python\}\n(.*?)\n```", chapter, flags=re.DOTALL)

    artifact_dir = tmp_path / "examples" / "_artifacts" / "fremtpl2"
    artifact_dir.mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "azoic-chapter-smoke"\nversion = "0.0.0"\nrequires-python = ">=3.12"\n'
    )
    portfolio = make_synthetic_portfolio(n=4_000)
    rng = np.random.default_rng(42)
    portfolio = portfolio.assign(
        policy_id=np.arange(len(portfolio)),
        bonus_malus=rng.integers(50, 100, len(portfolio)),
        density=rng.uniform(1, 100, len(portfolio)),
        veh_power=rng.choice(["4", "5", "6"], len(portfolio)),
        veh_gas=rng.choice(["diesel", "regular"], len(portfolio)),
        area=rng.choice(["A", "B"], len(portfolio)),
    )
    raw = portfolio.rename(
        columns={
            "policy_id": "IDpol",
            "exposure": "Exposure",
            "claim_count": "ClaimNb",
            "claim_amount": "ClaimAmount",
            "driver_age": "DrivAge",
            "vehicle_age": "VehAge",
            "bonus_malus": "BonusMalus",
            "density": "Density",
            "region": "Region",
            "vehicle_brand": "VehBrand",
            "veh_power": "VehPower",
            "veh_gas": "VehGas",
            "area": "Area",
        }
    )
    raw_frames = {
        41214: raw.drop(columns="ClaimAmount"),
        41215: raw.loc[raw["ClaimAmount"] > 0, ["IDpol", "ClaimAmount"]],
    }
    loader = _portfolio_loader(
        artifact_dir, lambda *, data_id, **kwargs: SimpleNamespace(frame=raw_frames[data_id])
    )
    loader["load_portfolio"]()
    assert not list(artifact_dir.glob("*.xlsx"))
    preamble = """
import sklearn.datasets

def reject_download(*args, **kwargs):
    raise AssertionError("Chapter smoke test must use only its synthetic cache")

sklearn.datasets.fetch_openml = reject_download
"""
    checks = """
assert len(mlflow_run_ids) == 2
assert {path.name for path in artifacts} == {
    "model_card_tariff_structured.md", "model_card_raw_feature.md", "comparison_dashboard.html"
}
assert not list(ARTIFACT_DIR.glob("*.xlsx"))
"""
    if chapter_name == "02-experiments.qmd":
        checks = """
canonical_run = run_experiment(make_experiment_configs(str(PORTFOLIO_PATH))[0])
assert glm_run.train_indices == canonical_run.train_indices
assert glm_run.test_indices == canonical_run.test_indices
assert glm_config.name == "fremtpl2-tariff-structured"
assert gbm_config.name == "fremtpl2-raw-feature"
assert set(estimators) == {
    "direct-tweedie-glm", "tweedie-lightgbm-tariff", "tweedie-lightgbm"
}
assert (glm_config, gbm_config) == make_experiment_configs(str(PORTFOLIO_PATH))
"""
    if chapter_name == "04-scoring-tariff.qmd":
        scoring_cells = [
            cell
            for cell in cells
            if "scoring_frame =" in cell or "worked_policy =" in cell or "worked_price =" in cell
        ]
        checks = (
            """
assert len(final_metrics) == 8
assert direct_tariff_path.exists() and tariff_path.exists()
assert worked_policy["policy_id"].iloc[0] == test_frame["policy_id"].min()
pd.testing.assert_series_equal(scored["policy_id"], portfolio["policy_id"])
np.testing.assert_allclose(
    worked_price["raw_rate"], direct_pipeline.predict(worked_inputs), rtol=1e-6, atol=1e-8,
)
np.testing.assert_allclose(
    worked_price["raw_rate"],
    direct_tariff["base_rate"] * worked_factors["Selected factor"].prod(),
)
original_scored = scored.copy()
original_price = worked_price.copy()
portfolio = portfolio.drop(columns=["claim_amount", "claim_count"])
test_frame = test_frame.drop(columns=["claim_amount", "claim_count"]).sample(frac=1)
"""
            + "\n".join(scoring_cells)
            + """
pd.testing.assert_frame_equal(scored, original_scored)
pd.testing.assert_frame_equal(worked_price, original_price)
assert set(worked_inputs.columns) == {*FEATURES, "exposure"}
for name, estimator in estimators.items():
    raw = estimator.predict(scoring_frame)
    np.testing.assert_allclose(scored[f"{name}__raw_rate"], raw)
    np.testing.assert_allclose(
        scored[f"{name}__adjusted_rate"], raw * recalibration_factors[name],
    )
    for scale in ["raw", "adjusted"]:
        np.testing.assert_allclose(
            scored[f"{name}__{scale}_expected_period_cost"],
            scored[f"{name}__{scale}_rate"] * scored["exposure"],
        )
portfolio["exposure"] *= 2
test_frame["exposure"] *= 2
"""
            + "\n".join(scoring_cells)
            + """
for name in estimators:
    for scale in ["raw", "adjusted"]:
        np.testing.assert_allclose(
            scored[f"{name}__{scale}_rate"], original_scored[f"{name}__{scale}_rate"],
        )
        np.testing.assert_allclose(
            scored[f"{name}__{scale}_expected_period_cost"],
            2 * original_scored[f"{name}__{scale}_expected_period_cost"],
        )
for scale in ["raw", "adjusted"]:
    np.testing.assert_allclose(worked_price[f"{scale}_rate"], original_price[f"{scale}_rate"])
    np.testing.assert_allclose(
        worked_price[f"{scale}_expected_period_cost"],
        2 * original_price[f"{scale}_expected_period_cost"],
    )
"""
        )
    if chapter_name == "06-frequency-severity.qmd":
        preamble += "\nimport sys\nsys.modules['mlflow'] = None\n"
        prediction_cell = next(cell for cell in cells if "component_predictions = {}" in cell)
        calibration_cell = next(cell for cell in cells if "component_tables = {}" in cell)
        checks = (
            """
assert (claim_counts == 0).any() and (claim_counts > 1).any()
assert len(appendix_rows) == 4
assert {path.name for path in ARTIFACT_DIR.iterdir()} == {
    "fremtpl2_joined_v3.parquet", "cleaning_audit_v1.csv", "portfolio_v3.parquet",
}
for name, tables in component_tables.items():
    predictions = component_predictions[name]
    freq, sev = tables["frequency"], tables["severity"]
    np.testing.assert_allclose(freq["Exposure (insured years)"].sum(), w_test.sum())
    np.testing.assert_allclose(freq["Observed claims"].sum(), claim_counts.sum())
    np.testing.assert_allclose(
        freq["Predicted claims"].sum(), predictions["frequency"] @ w_test,
    )
    np.testing.assert_allclose(sev["Claim count"].sum(), claim_counts.sum())
    np.testing.assert_allclose(sev["Observed amount"].sum(), y_test.sum())
    np.testing.assert_allclose(
        sev["Predicted amount"].sum(), predictions["severity"] @ claim_counts,
    )
    np.testing.assert_allclose(
        predictions["raw_product"], predictions["frequency"] * predictions["severity"],
    )
    np.testing.assert_allclose(
        predictions["raw_product"], fs_estimators[name].predict(component_inputs),
    )
original_predictions = component_predictions.copy()
test_frame = test_frame.drop(columns=["claim_count", "claim_amount"])
"""
            + prediction_cell
            + """
for name, predictions in component_predictions.items():
    pd.testing.assert_frame_equal(predictions, original_predictions[name])

test_frame["claim_count"] = claim_counts
original_calibration = calibration_table
calibration_calls = []
def checked_calibration(observed, predicted, weights, **kwargs):
    calibration_calls.append((np.asarray(observed), np.asarray(predicted), np.asarray(weights)))
    return original_calibration(observed, predicted, weights, **kwargs)
calibration_table = checked_calibration
"""
            + calibration_cell
            + """
assert len(calibration_calls) == 4
for index, predictions in enumerate(component_predictions.values()):
    for actual, expected in zip(calibration_calls[2 * index],
        [claim_counts, predictions["frequency"], w_test], strict=True):
        np.testing.assert_array_equal(actual, expected)
    mask = claim_counts > 0
    for actual, expected in zip(calibration_calls[2 * index + 1],
        [y_test[mask], predictions["severity"].to_numpy()[mask], claim_counts[mask]], strict=True):
        np.testing.assert_array_equal(actual, expected)
"""
        )
    if chapter_name == "07-tuning.qmd":
        checks = """
assert baseline_config.tuning is None
assert baseline_config.models == make_experiment_configs(str(subset_path))[0].models
for field in [
    "data_path", "spec", "features", "preprocessing", "split", "test_size", "random_state",
]:
    assert getattr(baseline_config, field) == getattr(tuning_config, field)
assert baseline_run.data_fingerprint == result.run.data_fingerprint
assert baseline_run.train_indices == result.run.train_indices
assert baseline_run.test_indices == result.run.test_indices
spaces = tuning_config.tuning.search_space
assert set(spaces) == {"direct-tweedie-glm", "tweedie-lightgbm-tariff"}
assert set(spaces["direct-tweedie-glm"]) == {"alpha"}
alpha = spaces["direct-tweedie-glm"]["alpha"]
assert (alpha.low, alpha.high, alpha.log, alpha.step) == (1e-4, 0.1, True, None)
assert set(spaces["tweedie-lightgbm-tariff"]) == {"num_leaves"}
leaves = spaces["tweedie-lightgbm-tariff"]["num_leaves"]
assert (leaves.low, leaves.high, leaves.step, leaves.log) == (8, 32, 8, False)
assert 1e-4 <= result.best_params["direct-tweedie-glm"]["alpha"] <= 0.1
assert result.best_params["tweedie-lightgbm-tariff"]["num_leaves"] in [8, 16, 24, 32]
assert result.n_trials == 8 and tuning_config.tuning.calibration_penalty == 1.0
np.testing.assert_allclose(penalty_contribution, 0.1)
for name, base in baseline_run.models.items():
    assert set(result.best_params[name]) == set(spaces[name])
    for parameter, value in base.params.items():
        if parameter not in spaces[name]:
            assert result.run.models[name].params[parameter] == value
    prediction = result.estimators[name].predict(outer_test[[*FEATURES, "exposure"]])
    actual = holdout_diagnostics(outer_test.claim_amount, outer_test.exposure, prediction)
    for label, metric in metric_names.items():
        np.testing.assert_allclose(comparison.loc[name, ("Untuned", label)], base.metrics[metric])
        np.testing.assert_allclose(comparison.loc[name, ("Tuned", label)], actual[metric])
assert ExperimentConfig.from_yaml(tuning_yaml) == tuning_config
assert tuned_card.stat().st_size > 0 and tuned_tariff_path.stat().st_size > 0

changed = tuning_subset.copy()
changed.loc[list(result.run.test_indices), "claim_amount"] *= 10
changed_path = ARTIFACT_DIR / "changed_outer.parquet"
changed.to_parquet(changed_path, index=False)
modified = tune_experiment(tuning_config.model_copy(update={"data_path": str(changed_path)}))
assert modified.best_params == result.best_params
np.testing.assert_allclose(list(modified.best_values.values()), list(result.best_values.values()))
assert modified.run.train_indices == result.run.train_indices
assert modified.run.test_indices == result.run.test_indices
assert modified.run.models["direct-tweedie-glm"].metrics["deviance_test"] != (
    result.run.models["direct-tweedie-glm"].metrics["deviance_test"]
)
"""
    completed = subprocess.run(
        [sys.executable, "-c", preamble + "\n".join(cells) + checks],
        cwd=tmp_path,
        env={
            **os.environ,
            "OMP_NUM_THREADS": "2",
            "OPENBLAS_NUM_THREADS": "2",
            "MKL_NUM_THREADS": "2",
            "MPLBACKEND": "Agg",
            "UV_PROJECT_ENVIRONMENT": sys.prefix,
            "UV_NO_SYNC": "1",
            "UV_OFFLINE": "1",
        },
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_protected_age_band_labels_match_chapter_boundaries():
    chapter = (Path(__file__).parents[1] / "examples" / "09-protected-group.qmd").read_text()
    cell = re.findall(r"```\{python\}\n(.*?)\n```", chapter, flags=re.DOTALL)[0]
    assignment = next(
        node
        for node in ast.parse(cell).body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Subscript)
        and ast.literal_eval(node.targets[0].slice) == "driver_age_band"
    )
    frame = pd.DataFrame({"driver_age": [29, 30, 31, 55, 56]})
    exec(
        compile(ast.Module(body=[assignment], type_ignores=[]), "<age-band>", "exec"),
        {"pd": pd, "audit_subset": frame},
    )
    assert frame["driver_age_band"].tolist() == [
        "30_and_under",
        "30_and_under",
        "over_30_to_55",
        "over_30_to_55",
        "over_55",
    ]
    np.testing.assert_array_equal(
        pd.Categorical(
            frame["driver_age_band"], categories=["30_and_under", "over_30_to_55", "over_55"]
        ).codes,
        pd.cut(frame["driver_age"], bins=[17, 30, 55, 120]).cat.codes,
    )


def test_own_portfolio_example_predicts_rates_and_period_costs(tmp_path, monkeypatch):
    chapter = (Path(__file__).parents[1] / "examples" / "02-experiments.qmd").read_text()
    section = chapter.split("## Use your own portfolio")[1]
    snippet = re.search(r"```python\n(.*?)\n```", section, flags=re.DOTALL).group(1)
    portfolio = make_synthetic_portfolio(n=1_000).rename(
        columns={"claim_amount": "paid_claims", "exposure": "insured_years"}
    )
    portfolio.to_parquet(tmp_path / "my_portfolio.parquet", index=False)
    monkeypatch.chdir(tmp_path)
    namespace = {}
    exec(snippet, namespace)
    scored = namespace["scored"]
    assert len(scored) == 200
    assert "paid_claims" not in namespace["scoring_rows"]
    assert np.isfinite(scored["raw_rate"]).all()
    assert scored["raw_rate"].gt(0).all()
    np.testing.assert_allclose(
        scored["expected_period_cost"], scored["raw_rate"] * scored["insured_years"]
    )
    doubled_exposure = namespace["scoring_rows"].copy()
    doubled_exposure["insured_years"] *= 2
    np.testing.assert_allclose(
        namespace["my_estimators"]["direct-glm"].predict(doubled_exposure),
        scored["raw_rate"],
    )


@pytest.mark.parametrize("preprocessing", [None, {"binner": {"cols": ["driver_age"]}}])
def test_operations_scoring_excludes_metadata(tmp_path, preprocessing):
    from azoic.data import DatasetSpec
    from azoic.workflow import ExperimentConfig, ModelSpec

    guide = (Path(__file__).parents[1] / "docs" / "guide" / "operations.md").read_text()
    section = guide.split("## Score an outcome-free frame")[1]
    snippet = re.search(r"```python\n(.*?)\n```", section, flags=re.DOTALL).group(1)
    portfolio = make_synthetic_portfolio(n=1_000).rename(columns={"exposure": "insured_years"})
    portfolio["policy_id"] = [f"policy-{i}" for i in range(len(portfolio))]
    portfolio["note"] = "review only"
    path = tmp_path / "portfolio.parquet"
    portfolio.to_parquet(path)
    config = ExperimentConfig(
        data_path=str(path),
        spec=DatasetSpec(
            target="claim_amount", exposure="insured_years", claim_count="claim_count"
        ),
        features=["vehicle_age", "driver_age"],
        preprocessing=preprocessing,
        models={"tweedie-glm": ModelSpec(params={"family": "tweedie", "link": "log"})},
    )
    test = portfolio.drop(columns=["claim_amount", "claim_count"]).sample(n=50, random_state=42)
    namespace = {"config": config, "test": test}
    exec(snippet, namespace)
    assert list(namespace["unlabeled"]) == ["vehicle_age", "driver_age", "insured_years"]
    scored = namespace["scored"]
    pd.testing.assert_series_equal(scored["policy_id"], test["policy_id"])
    assert np.isfinite(scored["predicted_rate"]).all()
    assert scored["predicted_rate"].gt(0).all()
    np.testing.assert_allclose(
        scored["expected_period_cost"], scored["predicted_rate"] * test["insured_years"]
    )


def test_temporal_chapter_selects_positions_with_policy_id_index(tmp_path):
    from azoic.data import DatasetSpec
    from azoic.metrics import stability_table
    from azoic.workflow import ExperimentConfig, ModelSpec, run_experiment

    chapter = (Path(__file__).parents[1] / "examples" / "08-temporal-stability.qmd").read_text()
    cells = re.findall(r"```\{python\}\n(.*?)\n```", chapter, flags=re.DOTALL)
    portfolio = make_synthetic_portfolio(n=2_400).assign(period=np.repeat(np.arange(24), 100))
    portfolio.index = pd.Index([f"policy-{i}" for i in range(len(portfolio))], name="policy_id")
    path = tmp_path / "portfolio.parquet"
    portfolio.to_parquet(path)
    namespace = {
        "np": np,
        "DatasetSpec": DatasetSpec,
        "ExperimentConfig": ExperimentConfig,
        "ModelSpec": ModelSpec,
        "run_experiment": run_experiment,
        "stability_table": stability_table,
        "portfolio": portfolio,
        "portfolio_path": path,
        "RANDOM_STATE": 42,
        "display": lambda *args: None,
    }
    for cell in cells:
        if "config = ExperimentConfig(" in cell or "test_frame =" in cell:
            exec(cell, namespace)
    assert namespace["train_periods"].tolist() == list(range(18))
    assert namespace["test_periods"].tolist() == list(range(18, 24))
    pd.testing.assert_frame_equal(namespace["test_frame"], portfolio.iloc[1_800:])
