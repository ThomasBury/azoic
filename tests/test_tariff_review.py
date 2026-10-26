"""M60: frozen, ID-aligned development review and reconciled evidence bundles."""

from copy import deepcopy

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure
from typer.testing import CliRunner

from azoic import (
    AutoBinner,
    AutoGrouper,
    DatasetSpec,
    ExperimentConfig,
    ModelSpec,
    PreprocessingSpec,
    RiskGBM,
    RiskGLM,
    revise_run,
    run_experiment,
    save_run,
    tariff_review,
)
from azoic.cli import app
from tests.conftest import make_synthetic_portfolio


@pytest.fixture(scope="module")
def journey():
    frame = make_synthetic_portfolio(n=360).assign(
        id=[f"policy-{i}" for i in range(360)], period=np.tile([2023, 2024, 2025], 120)
    )
    config = ExperimentConfig(
        data_path="not-read.parquet",
        features=["driver_age", "region"],
        spec=DatasetSpec(
            target="claim_amount",
            exposure="exposure",
            claim_count="claim_count",
            id_col="id",
            time_col="period",
            currency="EUR",
            protected_cols=["vehicle_brand"],
            claim_valuation_basis="paid at observation end",
        ),
        models={"glm": ModelSpec(params={"family": "tweedie", "link": "log"})},
        preprocessing=PreprocessingSpec(
            binner={
                "cols": ["driver_age"],
                "fixed": {"driver_age": {"edges": [25.0, 60.0], "closure": "left", "missing": 0}},
            }
        ),
    )
    run, fitted = run_experiment(config, df=frame, return_estimators=True)
    remapped_config = config.model_copy(deep=True)
    remapped_config.preprocessing.binner["fixed"]["driver_age"]["edges"] = [35.0, 60.0]
    remapped_run, remapped = run_experiment(remapped_config, df=frame, return_estimators=True)
    calibrated_run, calibrated = revise_run(run, fitted, model="glm", df=frame, replacements=[])
    revised_run, revised = revise_run(
        remapped_run,
        remapped,
        model="glm",
        df=frame,
        replacements=[
            {
                "feature": "driver_age",
                "level": "[35, 60)",
                "factor": 1.15,
                "reason": "Documented synthetic age review",
            }
        ],
    )
    incumbent = frame[["id"]].assign(old_rate=100.0)
    incumbent.loc[::31, "old_rate"] = 0.0
    candidates = {
        "fitted": (run, fitted),
        "remapped": (remapped_run, remapped),
        "recalibrated": (calibrated_run, calibrated),
        "revised": (revised_run, revised),
    }
    return frame, incumbent, candidates


def reject(*args, **kwargs):
    raise AssertionError("review must not fit or recalibrate")


def review(journey, out, **kwargs):
    frame, incumbent, runs = journey
    return tariff_review(
        runs,
        df=frame,
        incumbent=incumbent,
        incumbent_rate="old_rate",
        out=out,
        selected="revised/glm",
        rationale="Review age changes and totals.",
        segments=["region"],
        **kwargs,
    )


def test_review_complete_no_fit_journey_and_independent_totals(journey, tmp_path, monkeypatch):
    frame, incumbent, runs = journey
    expected = {
        f"{alias}/glm": estimators["glm"].predict(frame[list(estimators["glm"].feature_names_in_)])
        for alias, (_, estimators) in runs.items()
    }
    frozen = deepcopy(runs["revised"][0].models["glm"].revision)
    for cls in (RiskGLM, RiskGBM, AutoBinner, AutoGrouper):
        monkeypatch.setattr(cls, "fit", reject)
    monkeypatch.setattr("azoic.tariff.recalibrate_for_total", reject)
    shuffled = incumbent.sample(frac=1, random_state=9)
    path = review(
        (frame, shuffled, runs), tmp_path / "review", limitations=["Synthetic claims only."]
    )
    text = path.read_text()
    assert "Selected: **revised/glm**" in text and "Synthetic claims only." in text
    assert "not final-test evidence" in text and "undefined percentage changes" in text
    assert "EUR per exposure-year" in text and "paid at observation end" in text
    assert "Documented synthetic age review" in text
    assert "incumbent" in text and len(list(path.parent.glob("*.png"))) == 7
    records = pd.read_csv(path.parent / "records.csv")
    totals = pd.read_csv(path.parent / "totals.csv")
    assert len(records) == len(frame) * 5
    for label, rates in {"incumbent": incumbent.old_rate.to_numpy(), **expected}.items():
        rows = records[records.candidate == label]
        assert rows.record_id.tolist() == frame.id.tolist()
        np.testing.assert_allclose(rows.rate, rates, rtol=1e-14)
        np.testing.assert_allclose(rows.predicted_claim_amount, rates * frame.exposure, rtol=1e-14)
        assert rows.loc[incumbent.old_rate.to_numpy() == 0, "percentage_change"].isna().all()
        mask = incumbent.old_rate.to_numpy() > 0
        np.testing.assert_allclose(
            rows.percentage_change.to_numpy()[mask], 100 * (rates[mask] / 100 - 1), atol=1e-12
        )
        for partition, positions in (
            ("development", np.arange(len(frame))),
            ("training", runs["fitted"][0].train_indices),
            ("validation", runs["fitted"][0].test_indices),
        ):
            selected = totals[(totals.candidate == label) & (totals.partition == partition)].iloc[0]
            subset = frame.iloc[list(positions)]
            assert selected.n_records == len(subset)
            assert selected.exposure == pytest.approx(subset.exposure.sum())
            assert selected.claim_amount == pytest.approx(subset.claim_amount.sum())
            assert selected.claim_count == subset.claim_count.sum()
            predicted = np.dot(rates[list(positions)], subset.exposure)
            assert selected.predicted_claim_amount == pytest.approx(predicted)
            assert selected.o_p_ratio == pytest.approx(subset.claim_amount.sum() / predicted)
    training = totals[
        (totals.candidate.isin(["recalibrated/glm", "revised/glm"]))
        & (totals.partition == "training")
    ]
    np.testing.assert_allclose(training.o_p_ratio, 1, rtol=1e-12)
    for name in ("segments", "temporal", "rate_changes"):
        table = pd.read_csv(path.parent / f"{name}.csv")
        keys = ["candidate", "partition", *(["feature"] if name == "segments" else [])]
        grouped = table.groupby(keys)[["exposure", "claim_amount", "predicted_claim_amount"]].sum()
        for key, row in grouped.iterrows():
            baseline = totals[(totals.candidate == key[0]) & (totals.partition == key[1])].iloc[0]
            np.testing.assert_allclose(row, baseline[row.index].to_numpy(dtype=float))
    mappings = pd.read_csv(path.parent / "mapping_changes.csv")
    assert "35.0" in mappings.to_string() and mappings.candidate.eq("remapped/glm").any()
    factors = pd.read_csv(path.parent / "factor_changes.csv")
    assert factors.candidate.eq("revised/glm").any()
    assert frozen == runs["revised"][0].models["glm"].revision
    assert plt.get_fignums() == []
    for csv in path.parent.glob("*.csv"):
        assert f"]({csv.name})" in text
        pd.read_csv(csv)


@pytest.mark.parametrize(
    "issue", ["duplicate", "missing", "extra", "null", "negative", "nan", "inf"]
)
def test_review_rejects_bad_incumbent_before_writing(journey, tmp_path, issue):
    frame, incumbent, runs = journey
    incumbent = incumbent.copy()
    if issue == "duplicate":
        incumbent.loc[1, "id"] = incumbent.loc[0, "id"]
    elif issue == "missing":
        incumbent = incumbent.iloc[1:]
    elif issue == "extra":
        incumbent.loc[0, "id"] = "unexpected"
    elif issue == "null":
        incumbent.loc[0, "id"] = None
    else:
        incumbent.loc[0, "old_rate"] = {"negative": -1, "nan": np.nan, "inf": np.inf}[issue]
    with pytest.raises(ValueError):
        review((frame, incumbent, runs), tmp_path / "review")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "issue", ["fingerprint", "basis", "membership", "ids", "no_ids", "split_overlap"]
)
def test_review_rejects_mixed_or_invalid_context(journey, tmp_path, issue):
    frame, incumbent, all_runs = journey
    run, fitted = all_runs["fitted"]
    config = run.config.model_copy(deep=True)
    updates = {}
    if issue == "fingerprint":
        updates["data_fingerprint"] = "other"
    elif issue == "basis":
        config.spec.currency = "USD"
    elif issue == "membership":
        updates["test_indices"] = (run.train_indices[0], *run.test_indices[1:])
    elif issue == "ids":
        updates["record_ids"] = tuple(reversed(run.record_ids))
    elif issue == "no_ids":
        updates["record_ids"] = ()
    else:
        updates["train_indices"] = (run.test_indices[0], *run.train_indices[1:])
    other = run.model_copy(update={"config": config, **updates})
    runs = {"fitted": (run, fitted), "revised": (other, fitted)}
    if issue in {"no_ids", "split_overlap"}:
        runs = {"revised": (other, fitted)}
    with pytest.raises(ValueError):
        review((frame, incumbent, runs), tmp_path / "review")
    assert list(tmp_path.iterdir()) == []


def test_review_rejects_changed_source_and_preserves_existing_bundle(journey, tmp_path):
    frame, incumbent, runs = journey
    with pytest.raises(ValueError, match="fingerprint"):
        review((frame.iloc[::-1], incumbent, runs), tmp_path / "review")
    out = tmp_path / "review"
    out.mkdir()
    (out / "review.md").write_text("previous evidence")
    with pytest.raises(FileExistsError):
        review(journey, out)
    assert (out / "review.md").read_text() == "previous evidence"


@pytest.mark.parametrize("failure", ["csv", "plot"])
def test_review_failure_cleans_partial_bundle(journey, tmp_path, monkeypatch, failure):
    def fail(*args, **kwargs):
        raise OSError("simulated save failure")

    monkeypatch.setattr(
        pd.DataFrame if failure == "csv" else Figure,
        "to_csv" if failure == "csv" else "savefig",
        fail,
    )
    with pytest.raises(OSError, match="simulated"):
        review(journey, tmp_path / "review")
    assert list(tmp_path.iterdir()) == []
    assert plt.get_fignums() == []


def test_review_cli_saved_candidates_without_fit(journey, tmp_path, monkeypatch):
    frame, incumbent, runs = journey
    for alias in ("fitted", "revised"):
        save_run(*runs[alias], tmp_path / f"{alias}.pkl")
    frame.to_parquet(tmp_path / "development.parquet")
    incumbent.iloc[::-1].to_parquet(tmp_path / "incumbent.parquet")
    monkeypatch.setattr(RiskGLM, "fit", reject)
    monkeypatch.setattr("azoic.tariff.recalibrate_for_total", reject)
    result = CliRunner().invoke(
        app,
        [
            "report",
            "--review",
            "--run",
            str(tmp_path / "fitted.pkl"),
            "--run",
            str(tmp_path / "revised.pkl"),
            "--data",
            str(tmp_path / "development.parquet"),
            "--incumbent",
            str(tmp_path / "incumbent.parquet"),
            "--incumbent-rate",
            "old_rate",
            "--selected",
            "revised/glm",
            "--rationale",
            "Age selection evidence",
            "--segment",
            "region",
            "--out",
            str(tmp_path / "review"),
        ],
    )
    assert result.exit_code == 0, (result.output, result.exception)
    assert (tmp_path / "review" / "review.md").exists()
    missing = CliRunner().invoke(app, ["report", "--review", "--run", str(tmp_path / "fitted.pkl")])
    assert missing.exit_code == 2 and "requires" in missing.output


def test_review_zero_rates_missing_counts_periods_and_default_segments(journey, tmp_path):
    frame, incumbent, runs = journey
    run, fitted = runs["fitted"]
    config = run.config.model_copy(deep=True)
    config.spec.time_col = config.spec.claim_count = None
    revised_run, revised = revise_run(
        run, fitted, model="glm", df=frame, replacements=[], recalibrate=False
    )
    revised["glm"].tariff["base_rate"] = 0.0
    revised["glm"].revision["structural_base"] = 0.0
    revised_run = revised_run.model_copy(update={"config": config})
    revised_run.models["glm"].revision["structural_base"] = 0.0
    path = tariff_review(
        {"zero": (revised_run, revised)},
        df=frame,
        incumbent=incumbent,
        incumbent_rate="old_rate",
        selected="zero/glm",
        out=tmp_path / "zero",
        rationale="Zero-rate diagnostic edge case",
    )
    totals = pd.read_csv(path.parent / "totals.csv")
    zero = totals[totals.candidate == "zero/glm"]
    assert zero.predicted_claim_amount.eq(0).all() and zero.o_p_ratio.isna().all()
    assert zero.deviance.eq(np.inf).all() and zero.d2.isna().all()
    assert totals.claim_count.isna().all()
    assert pd.read_csv(path.parent / "temporal.csv").empty
    assert set(pd.read_csv(path.parent / "segments.csv").feature) == {
        "driver_age",
        "region",
        "vehicle_brand",
    }
    assert "no time_col" in path.read_text() and "Claim counts unavailable" in path.read_text()


def test_review_missing_segments_raw_gbm_and_multiple_models(journey, tmp_path):
    frame, incumbent, runs = journey
    frame = frame.copy()
    frame.loc[::7, "vehicle_brand"] = np.nan
    config = runs["fitted"][0].config.model_copy(deep=True)
    config.models["gbm"] = ModelSpec(
        kind="gbm", preprocess=False, params={"n_estimators": 3, "n_jobs": 1}
    )
    run, fitted = run_experiment(config, df=frame, return_estimators=True)
    path = tariff_review(
        {"fit": (run, fitted)},
        df=frame,
        incumbent=incumbent,
        incumbent_rate="old_rate",
        out=tmp_path / "review",
        selected="fit/gbm",
        rationale="Descriptive GBM benchmark",
        segments=["vehicle_brand"],
    )
    table = pd.read_csv(path.parent / "segments.csv")
    assert table.level.isna().any()
    for (_, partition), rows in table.groupby(["candidate", "partition"]):
        positions = (
            np.arange(len(frame))
            if partition == "development"
            else (run.train_indices if partition == "training" else run.test_indices)
        )
        assert rows.exposure.sum() == pytest.approx(frame.iloc[list(positions)].exposure.sum())
    metadata = pd.read_csv(path.parent / "candidates.csv")
    assert (
        metadata.loc[metadata.candidate == "fit/gbm", "factor_status"].iloc[0]
        == "not a log-link GLM tariff"
    )
    assert pd.read_csv(path.parent / "factors.csv").candidate.eq("fit/glm").all()


@pytest.mark.parametrize("issue", ["negative", "nonfinite", "column", "overflow"])
def test_review_rejects_invalid_predictions(journey, tmp_path, monkeypatch, issue):
    _, _, runs = journey
    estimator = runs["fitted"][1]["glm"]
    if issue == "column":
        monkeypatch.setattr(estimator, "predict", lambda X: np.ones((len(X), 1)))
    else:
        value = {"negative": -1, "nonfinite": np.nan, "overflow": 1e308}[issue]
        monkeypatch.setattr(estimator, "predict", lambda X: np.full(len(X), value))
    with pytest.raises(ValueError, match="finite"):
        review(journey, tmp_path / "review")
    assert list(tmp_path.iterdir()) == []
