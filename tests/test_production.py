"""Final evidence belongs to the evaluated fit; production fits get fresh evidence."""

import json
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from azoic import (
    DatasetSpec,
    ExperimentConfig,
    ModelSpec,
    PreprocessingSpec,
    evaluate_final,
    export_production,
    load_run,
    refit_production,
    revise_run,
    run_experiment,
    save_run,
    split_portfolio,
)
from azoic.models import RiskGLM
from azoic.preprocessing import AutoBinner, AutoGrouper
from tests.conftest import make_synthetic_portfolio


@pytest.fixture
def journey():
    full = make_synthetic_portfolio(n=600).assign(record_id=np.arange(600))
    development, final = full.iloc[:480].copy(), full.iloc[480:].copy()
    config = ExperimentConfig(
        data_path="unused.parquet",
        spec=DatasetSpec(
            target="claim_amount",
            exposure="exposure",
            claim_count="claim_count",
            id_col="record_id",
            currency="EUR",
        ),
        features=["driver_age", "region"],
        preprocessing=PreprocessingSpec(
            binner={"cols": ["driver_age"], "max_bins": 3},
            grouper={"cols": ["region"], "max_groups": 2},
        ),
        models={"glm": ModelSpec(params={"family": "tweedie", "link": "log"})},
    )
    run, models = run_experiment(config, df=development, return_estimators=True)
    return full, development, final, run, models


def evaluated(journey):
    _, _, final, run, models = journey
    result = evaluate_final(
        run,
        models,
        model="glm",
        df=final,
        final_test_ids=final.record_id.tolist(),
        rationale="Frozen selection",
    )
    return result, models


def reject(*args, **kwargs):
    raise AssertionError("this operation must not fit or recalibrate")


def test_final_evaluation_no_fit_or_recalibration_and_independent_metrics(journey, monkeypatch):
    import azoic.tariff
    from azoic.metrics import mean_tweedie_deviance

    _, _, final, run, models = journey
    for cls in (RiskGLM, AutoBinner, AutoGrouper):
        monkeypatch.setattr(cls, "fit", reject)
    monkeypatch.setattr(azoic.tariff, "recalibrate_for_total", reject)
    result, _ = evaluated(journey)
    assert not run.final_evaluation
    assert not result.production
    assert result.models["glm"].metrics == run.models["glm"].metrics
    rates = models["glm"].predict(final[list(models["glm"].feature_names_in_)])
    metrics = result.final_evaluation["metrics"]
    assert metrics["predicted_total"] == pytest.approx(np.dot(rates, final.exposure))
    assert metrics["op_ratio"] == pytest.approx(
        final.claim_amount.sum() / np.dot(rates, final.exposure)
    )
    assert metrics["deviance"] == pytest.approx(
        mean_tweedie_deviance(
            final.claim_amount / final.exposure, rates, sample_weight=final.exposure, power=1.5
        )
    )
    with pytest.raises(ValueError, match="unevaluated"):
        evaluate_final(
            result,
            models,
            model="glm",
            df=final,
            final_test_ids=final.record_id.tolist(),
            rationale="Again",
        )


@pytest.mark.parametrize("problem", ["overlap", "missing", "duplicate", "extra", "invalid"])
def test_final_membership_and_outcomes(journey, problem):
    _, _, final, run, models = journey
    final = final.copy()
    ids = final.record_id.tolist()
    if problem == "overlap":
        final.loc[final.index[0], "record_id"] = 0
        ids = final.record_id.tolist()
    elif problem == "missing":
        ids = ids[:-1]
    elif problem == "duplicate":
        ids.append(ids[0])
    elif problem == "extra":
        ids.append(999)
    else:
        final.loc[final.index[0], "exposure"] = 0
    with pytest.raises(ValueError):
        evaluate_final(run, models, model="glm", df=final, final_test_ids=ids, rationale="Selected")


def test_refit_freezes_mappings_and_keeps_holdout_with_predecessor(journey, monkeypatch):
    full, _, _, original, models = journey
    run, models = evaluated(journey)
    before = models["glm"].predict(full[list(models["glm"].feature_names_in_)])
    monkeypatch.setattr(AutoBinner, "fit", reject)
    monkeypatch.setattr(AutoGrouper, "fit", reject)
    production, fitted = refit_production(
        run, models, df=full.sample(frac=1, random_state=7), rationale="Approved full fit"
    )
    assert not production.final_evaluation
    assert production.production["predecessor_final_evaluation"] == run.final_evaluation
    assert production.n_test == 0 and production.n_train == len(full)
    assert all(key.endswith("_full") for key in production.models["glm"].metrics)
    for name in ("binner", "grouper"):
        old, new = models["glm"].named_steps[name], fitted["glm"].named_steps[name]
        pd.testing.assert_frame_equal(
            old.transform(full[list(old.feature_names_in_)]),
            new.transform(full[list(new.feature_names_in_)]),
        )
    np.testing.assert_array_equal(
        before, models["glm"].predict(full[list(models["glm"].feature_names_in_)])
    )
    assert not original.final_evaluation
    assert not np.array_equal(
        before, fitted["glm"].predict(full[list(fitted["glm"].feature_names_in_)])
    )


def test_refit_restores_saved_partition_categories_without_rounding(journey, tmp_path, monkeypatch):
    full, _, _, original, _ = journey
    full.index = pd.Index(np.arange(len(full)) * 7 + 11, name="policy_row")
    final_mask = full.record_id % 5 == 0
    full["region"] = pd.Categorical(
        np.where(final_mask, np.where(full.record_id % 2, "coastal", "rural"), "urban"),
        categories=["urban", "rural", "coastal", "unused"],
        ordered=True,
    )
    large = 2**63 + 1
    full["excluded_code"] = pd.Categorical.from_codes(
        np.where(full.record_id % 3 == 0, -1, final_mask.astype(int)),
        categories=pd.Index([large, large + 2], dtype="uint64"),
        ordered=True,
    )
    final_ids = full.loc[final_mask, "record_id"].tolist()
    development, final = split_portfolio(full, final_ids, id_col="record_id")
    final["region"] = final.region.cat.reorder_categories(["coastal", "rural"])
    assert development.region.cat.categories.tolist() == ["urban"]
    assert final.region.cat.categories.tolist() == ["coastal", "rural"]

    config = original.config.model_copy(deep=True)
    config.spec.excluded_cols = ["excluded_code"]
    config.preprocessing.grouper["fixed"] = {
        "region": {
            "groups": [{"level": level, "group": level} for level in ("urban", "rural", "coastal")],
            "missing": "rural",
            "unseen": "coastal",
        }
    }
    for name, frame in [("development", development), ("final", final)]:
        frame.to_pickle(tmp_path / f"{name}.pkl")
    development = pd.read_pickle(tmp_path / "development.pkl")
    final = pd.read_pickle(tmp_path / "final.pkl")
    artifact = tmp_path / "candidates.pkl"
    run, models = run_experiment(config, df=development, return_estimators=True)
    save_run(run, models, artifact)
    run, models = load_run(artifact)
    run, models = evaluated((full, development, final, run, models))
    save_run(run, models, artifact)
    run, models = load_run(artifact)

    production, fitted = refit_production(run, models, df=full, rationale="Approved")
    parts = [
        frame.assign(excluded_code=frame.excluded_code.astype(object).astype("UInt64"))
        for frame in (development, final)
    ]
    union = pd.concat(parts).loc[full.index]
    union.to_parquet(tmp_path / "lossless.parquet", index=True)
    restored, restored_models = refit_production(
        run, models, df=pd.read_parquet(tmp_path / "lossless.parquet"), rationale="Approved"
    )
    assert restored.data_fingerprint == production.data_fingerprint
    X = full[list(fitted["glm"].feature_names_in_)]
    np.testing.assert_allclose(
        fitted["glm"].predict(X), restored_models["glm"].predict(X), rtol=1e-12, atol=0
    )

    full.to_parquet(tmp_path / "rounded.parquet", index=True)
    monkeypatch.setattr("azoic.workflow._score_portfolio", reject)
    for lossy in (pd.concat([development, final]), pd.read_parquet(tmp_path / "rounded.parquet")):
        with pytest.raises(ValueError, match="categorical schema.*excluded_code"):
            refit_production(run, models, df=lossy, rationale="Approved")
    for changed in (
        full.reset_index(drop=True),
        full.iloc[:-1],
        full.assign(claim_amount=full.claim_amount * 2),
        full.assign(excluded_code=full.excluded_code.cat.remove_categories([large])),
    ):
        with pytest.raises(ValueError):
            refit_production(run, models, df=changed, rationale="Approved")


def test_refit_rejects_object_label_type_change_with_same_fixed_group(journey, monkeypatch):
    full, _, _, previous, _ = journey
    full["region"] = np.resize(np.array([1, "1", "other"], dtype=object), len(full))
    config = previous.config.model_copy(deep=True)
    config.preprocessing.grouper["fixed"] = {
        "region": {
            "groups": [
                {"level": 1, "group": "one"},
                {"level": "1", "group": "one"},
                {"level": "other", "group": "other"},
            ],
            "missing": "other",
            "unseen": "other",
        }
    }
    development, final = full.iloc[:480], full.iloc[480:]
    run, models = run_experiment(config, df=development, return_estimators=True)
    run, models = evaluated((full, development, final, run, models))
    changed = full.copy()
    changed.loc[0, "region"] = "1"
    grouper = models["glm"].named_steps["grouper"]
    grouper_input = list(grouper.feature_names_in_)
    pd.testing.assert_frame_equal(
        grouper.transform(full[grouper_input]), grouper.transform(changed[grouper_input])
    )
    monkeypatch.setattr("azoic.workflow._score_portfolio", reject)
    with pytest.raises(ValueError, match="development rows must match the original fingerprint"):
        refit_production(run, models, df=changed, rationale="Approved")


@pytest.mark.parametrize(
    "problem",
    [
        "no_evaluation",
        "changed_fit",
        "missing_row",
        "changed_development",
        "changed_final",
        "changed_basis",
        "changed_settings",
    ],
)
def test_refit_rejects_changed_identity(journey, problem):
    full, _, _, original, _ = journey
    run, models = evaluated(journey)
    full = full.copy()
    if problem == "no_evaluation":
        run = original
    elif problem == "changed_fit":
        models["glm"].named_steps["model"].backend_.intercept_ += 1
    elif problem == "missing_row":
        full = full.iloc[:-1]
    elif problem == "changed_basis":
        run.config.spec.currency = "GBP"
    elif problem == "changed_settings":
        run.config.models["glm"].params["alpha"] = 0.5
    else:
        row = 0 if problem == "changed_development" else 599
        full.loc[row, "claim_amount"] += 1
    with pytest.raises(ValueError):
        refit_production(run, models, df=full, rationale="Approved")


def test_revisions_reapply_latest_factor_and_calibrate_once(journey):
    full, development, _, run, models = journey
    from azoic.tariff import extract_tariff

    tariff = extract_tariff(models["glm"].named_steps["model"])
    feature = "region"
    level = next(iter(tariff["categorical"][feature]))
    for factor in (1.1, 1.3):
        run, models = revise_run(
            run,
            models,
            model="glm",
            df=development,
            replacements=[
                {"feature": feature, "level": level, "factor": factor, "reason": "Approved"}
            ],
        )
    updated = (*journey[:3], run, models)
    run, models = evaluated(updated)
    production, fitted = refit_production(run, models, df=full, rationale="Approved")
    revision = fitted["glm"].revision
    assert len(revision["changes"]) == 1
    assert revision["changes"][0]["factor"] == 1.3
    assert fitted["glm"].tariff["categorical"][feature][level] == 1.3
    assert np.dot(fitted["glm"].predict(full), full.exposure) == pytest.approx(
        full.claim_amount.sum()
    )
    assert production.models["glm"].revision["calibration"]["n_rows"] == len(full)
    with pytest.raises(ValueError, match="before final"):
        revise_run(production, fitted, model="glm", df=full, replacements=[])


def test_saved_evaluation_refit_and_handoff_fresh_process(journey, tmp_path):
    full, _, _, _, _ = journey
    run, models = evaluated(journey)
    save_run(run, models, tmp_path / "evaluated.pkl")
    run, models = load_run(tmp_path / "evaluated.pkl")
    production, fitted = refit_production(run, models, df=full, rationale="Approved")
    cases = pd.DataFrame({"driver_age": [25.0, 60.0], "region": ["urban", "rural"]})
    path = export_production(
        production,
        fitted,
        cases=cases,
        feature_units={"driver_age": "years", "region": "category"},
        out=tmp_path / "bundle",
    )
    spec = json.loads(path.read_text())
    assert spec["format"] == "azoic.production.1"
    assert spec["production"]["predecessor_final_evaluation"]["metrics"]
    assert len(spec["transformations"]) == 2
    import hashlib

    for filename, digest in spec["files_sha256"].items():
        assert hashlib.sha256((path.parent / filename).read_bytes()).hexdigest() == digest
    with pd.ExcelFile(path.parent / "tariff.xlsx") as workbook:
        assert workbook.sheet_names == ["base_rate", "factors", "mappings"]
    agreement = json.loads((path.parent / "agreement.json").read_text())
    assert any("-at" in row["case"] for row in agreement)
    assert any(row["outcome"] == "reject" for row in agreement)
    result = subprocess.run(
        [sys.executable, str(path.parent / "score.py")], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
    with pytest.raises(FileExistsError):
        export_production(
            production,
            fitted,
            cases=cases,
            feature_units={"driver_age": "years", "region": "category"},
            out=path.parent,
        )


def test_failed_handoff_preserves_previous_and_cleans_staging(journey, tmp_path, monkeypatch):
    import azoic.tariff

    full, _, _, _, _ = journey
    run, models = evaluated(journey)
    production, fitted = refit_production(run, models, df=full, rationale="Approved")

    def fail(*args, **kwargs):
        raise OSError("save failed")

    monkeypatch.setattr(azoic.tariff, "export_tariff", fail)
    with pytest.raises(OSError, match="save failed"):
        export_production(
            production,
            fitted,
            cases=pd.DataFrame({"driver_age": [25.0], "region": ["urban"]}),
            feature_units={"driver_age": "years", "region": "category"},
            out=tmp_path / "bundle",
        )
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("kind", ["glm", "gbm", "frequency_severity"])
def test_final_and_refit_support_all_existing_model_kinds(journey, tmp_path, kind):
    full, development, final, run, _ = journey
    config = run.config.model_copy(deep=True)
    config.preprocessing = None
    config.features = ["driver_age", "vehicle_age"]
    if kind == "frequency_severity":
        spec = ModelSpec(
            kind=kind,
            frequency=ModelSpec(params={"family": "poisson", "link": "log"}),
            severity=ModelSpec(params={"family": "gamma", "link": "log"}),
        )
    else:
        spec = ModelSpec(
            kind=kind,
            params={"n_estimators": 3, "n_jobs": 1}
            if kind == "gbm"
            else {"family": "tweedie", "link": "log"},
        )
    config.models = {kind: spec}
    run, models = run_experiment(config, df=development, return_estimators=True)
    result = evaluate_final(
        run,
        models,
        model=kind,
        df=final,
        final_test_ids=final.record_id.tolist(),
        rationale="Selected",
    )
    save_run(result, models, tmp_path / "evaluated.pkl")
    result, models = load_run(tmp_path / "evaluated.pkl")
    production, fitted = refit_production(result, models, df=full, rationale="Approved")
    assert set(fitted) == {kind}
    assert np.isfinite(fitted[kind].predict(full[list(fitted[kind].feature_names_in_)])).all()
    assert not production.final_evaluation
    save_run(production, fitted, tmp_path / "production.pkl")
    production, fitted = load_run(tmp_path / "production.pkl")
    if kind == "glm":
        export_production(
            production,
            fitted,
            cases=pd.DataFrame({"driver_age": [30.0], "vehicle_age": [4.0]}),
            feature_units={"driver_age": "years", "vehicle_age": "years"},
            out=tmp_path / "bundle",
        )


def test_production_reports_do_not_claim_holdout_scores(journey):
    from azoic import comparison_dashboard, comparison_table, model_card

    full, _, _, _, _ = journey
    run, models = evaluated(journey)
    assert "Frozen final evaluation" in model_card(run)
    production, _ = refit_production(run, models, df=full, rationale="Approved")
    card = model_card(production)
    assert "full training evidence only" in card
    assert "Full training evidence only" in card
    assert "gini (test)" not in card
    assert "Calibration table (full training" in card
    table = comparison_table([production])
    assert table.evidence.tolist() == ["production_refit (full training)"]
    with pytest.raises(ValueError, match="full-training"):
        comparison_dashboard([production])


def test_cli_final_refit_and_handoff(journey, tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from azoic.cli import app

    full, _, final, run, models = journey
    runner = CliRunner()
    source = tmp_path / "source.pkl"
    save_run(run, models, source)
    full.to_parquet(tmp_path / "full.parquet")
    final.to_parquet(tmp_path / "final.parquet")
    (tmp_path / "membership.json").write_text(json.dumps({"final_test": final.record_id.tolist()}))
    evaluated_path = tmp_path / "evaluated.pkl"
    with monkeypatch.context() as blocked:
        blocked.setattr(RiskGLM, "fit", reject)
        result = runner.invoke(
            app,
            [
                "evaluate-final",
                "--run",
                str(source),
                "--model",
                "glm",
                "--data",
                str(tmp_path / "final.parquet"),
                "--membership",
                str(tmp_path / "membership.json"),
                "--rationale",
                "Selected",
                "--out",
                str(evaluated_path),
            ],
        )
    assert result.exit_code == 0, result.output
    assert "Frozen final evaluation" in result.output
    production_path = tmp_path / "production.pkl"
    result = runner.invoke(
        app,
        [
            "refit-production",
            "--run",
            str(evaluated_path),
            "--data",
            str(tmp_path / "full.parquet"),
            "--rationale",
            "Approved",
            "--out",
            str(production_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "full training evidence only" in result.output
    pd.DataFrame({"driver_age": [30.0], "region": ["urban"]}).to_parquet(tmp_path / "cases.parquet")
    (tmp_path / "units.json").write_text(json.dumps({"driver_age": "years", "region": "category"}))
    with monkeypatch.context() as blocked:
        blocked.setattr(RiskGLM, "fit", reject)
        result = runner.invoke(
            app,
            [
                "export-production",
                "--run",
                str(production_path),
                "--cases",
                str(tmp_path / "cases.parquet"),
                "--units",
                str(tmp_path / "units.json"),
                "--out",
                str(tmp_path / "bundle"),
            ],
        )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "bundle/specification.json").exists()
    assert not load_run(source)[0].final_evaluation


@pytest.mark.parametrize("command", ["evaluate-final", "refit-production", "export-production"])
def test_new_cli_input_errors_are_actionable(tmp_path, command):
    from typer.testing import CliRunner

    from azoic.cli import app

    arguments = {
        "evaluate-final": [
            "--model",
            "glm",
            "--data",
            "missing",
            "--membership",
            "missing",
            "--rationale",
            "Selected",
        ],
        "refit-production": ["--data", "missing", "--rationale", "Approved"],
        "export-production": ["--cases", "missing", "--units", "missing"],
    }
    result = CliRunner().invoke(
        app,
        [
            command,
            "--run",
            str(tmp_path / "missing.pkl"),
            "--out",
            str(tmp_path / "out"),
            *arguments[command],
        ],
    )
    assert result.exit_code == 2, result.output
    assert "No such file" in result.output
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("revised", [False, True])
def test_workbook_specification_and_batch_recipe_agree(journey, tmp_path, monkeypatch, revised):
    from ast import literal_eval

    from azoic import tariff

    full, development, _, original, candidates = journey
    cases = pd.DataFrame({"driver_age": [30.0, 60.0], "region": ["urban", "rural"]})
    units = {"driver_age": "years", "region": "category"}
    if revised:
        full = full.assign(
            region=pd.Categorical.from_codes(
                np.resize([0, 1, -1, 2], len(full)), categories=[1, 2, 3]
            )
        )
        development, final = full.iloc[:480], full.iloc[480:]
        config = original.config.model_copy(deep=True)
        config.features.append("vehicle_age")
        config.preprocessing.grouper["fixed"] = {
            "region": {
                "groups": [
                    {"level": 1, "group": "one"},
                    {"level": 2, "group": "two"},
                    {"level": 3, "group": "unseen"},
                ],
                "missing": "missing",
                "unseen": "unseen",
            }
        }
        original, candidates = run_experiment(config, df=development, return_estimators=True)
        original, candidates = revise_run(
            original,
            candidates,
            model="glm",
            df=development,
            replacements=[
                {"feature": "region", "level": "unseen", "factor": 1.3, "reason": "Review"}
            ],
        )
        journey = (full, development, final, original, candidates)
        cases = cases.assign(region=[1.0, np.nan], vehicle_age=[4.1, 9.2])
        units["vehicle_age"] = "years"
    run, models = evaluated(journey)
    production, fitted = refit_production(run, models, df=full, rationale="Approved")

    workbook_parts = tariff._workbook_parts
    mapping_calls = []

    def describe_mappings(estimator):
        mapping_calls.append(estimator)
        return workbook_parts(estimator)

    monkeypatch.setattr(tariff, "_workbook_parts", describe_mappings)
    path = export_production(
        production,
        fitted,
        cases=cases,
        feature_units=units,
        out=tmp_path / "bundle",
    )
    spec = json.loads(path.read_text())
    agreements = json.loads((path.parent / "agreement.json").read_text())
    assert len(agreements) > len(cases) and len(mapping_calls) == 1
    assert any("-at" in case["case"] for case in agreements)
    assert any("-below" in case["case"] for case in agreements)
    assert any("-above" in case["case"] for case in agreements)
    sheets = pd.read_excel(path.parent / "tariff.xlsx", sheet_name=None)
    factors, mappings = sheets["factors"], sheets["mappings"]
    base = sheets["base_rate"].base_rate.iloc[0]
    bins = mappings.query("role == 'binned'").iloc[0]
    groups = mappings.query("role == 'grouped'").iloc[0]
    edges = [float(edge) for edge in str(bins.mapping).split(", ")]
    bin_labels = factors.query("feature == 'driver_age'").level.tolist()
    group_map = {
        (type(key), key): value
        for entry in groups.mapping.split("; ")
        for key, value in [tuple(map(literal_eval, entry.split(" -> ")))]
    }
    workbook_factors = {
        (row.feature, row.level): row.multiplicative_factor for row in factors.itertuples()
    }

    def score_workbook(values):
        age, region = values["driver_age"], values["region"]
        if pd.isna(age):
            age_band = bins.missing_destination
        else:
            if not np.isfinite(age):
                raise ValueError("nonfinite numeric")
            age_band = bin_labels[
                sum(
                    age > edge if bins.interval_closure == "right" else age >= edge
                    for edge in edges
                )
            ]
        group = (
            groups.missing_destination
            if pd.isna(region)
            else group_map.get((type(region), region), groups.unseen_destination)
        )
        result = base * workbook_factors["driver_age", age_band] * workbook_factors["region", group]
        if "vehicle_age" in values:
            value = values["vehicle_age"]
            if value is None or not np.isfinite(value):
                raise ValueError("missing/nonfinite numeric")
            result *= workbook_factors["vehicle_age", "_per_unit"] ** value
        return result

    def score_specification(values):
        values = values.copy()
        for transform in spec["transformations"]:
            for feature, mapping in transform["features"].items():
                value = values[feature]
                if transform["type"] == "bins":
                    if pd.isna(value):
                        bin_index = mapping["missing_bin"]
                    else:
                        if not np.isfinite(value):
                            raise ValueError("nonfinite numeric")
                        bin_index = sum(
                            value > edge if mapping["closure"] == "right" else value >= edge
                            for edge in mapping["edges"]
                        )
                    values[feature] = mapping["labels"][bin_index]
                else:
                    values[feature] = (
                        mapping["missing"]
                        if pd.isna(value)
                        else next(
                            (
                                entry["group"]
                                for entry in mapping["groups"]
                                if type(entry["level"]) is type(value) and entry["level"] == value
                            ),
                            mapping["unseen"],
                        )
                    )
        result = spec["base_rate"]
        for term in spec["numeric_terms"]:
            value = values[term["feature"]]
            if value is None or not np.isfinite(value):
                raise ValueError("missing/nonfinite numeric")
            result *= np.exp(term["log_coefficient"] * value)
        for term in spec["categorical_terms"]:
            value = values[term["feature"]]
            factor = next(
                entry["factor"]
                for entry in term["levels"]
                if type(entry["level"]) is type(value) and entry["level"] == value
            )
            result *= factor
        return result

    for case in agreements:
        values = {
            key: (float(value["$float"]) if isinstance(value, dict) else value)
            for key, value in case["input"].items()
        }
        if case["outcome"] == "reject":
            with pytest.raises(ValueError):
                score_workbook(values)
            with pytest.raises(ValueError):
                score_specification(values)
        else:
            assert score_workbook(values) == pytest.approx(case["expected_rate"], rel=1e-12)
            assert score_specification(values) == pytest.approx(case["expected_rate"], rel=1e-12)

    script = [sys.executable, str(path.parent / "score.py")]
    result = subprocess.run(script, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    batch = cases.assign(record_id=[81, 19], exposure=[0.637, 0.024])
    batch.to_parquet(tmp_path / "inputs.parquet")
    output = tmp_path / "rates.csv"
    result = subprocess.run(
        [*script, str(tmp_path / "inputs.parquet"), str(output)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
    rows = pd.read_csv(output)
    assert rows.record_id.tolist() == batch.record_id.tolist()
    expected = fitted["glm"].predict(cases)
    np.testing.assert_allclose(rows.predicted_rate, expected, rtol=1e-12, atol=0)
    np.testing.assert_allclose(
        rows.predicted_period_cost, expected * batch.exposure, rtol=1e-12, atol=0
    )
    np.testing.assert_allclose(
        [case["expected_rate"] for case in agreements if case["case"].startswith("synthetic-")],
        expected,
        rtol=1e-12,
        atol=0,
    )


@pytest.mark.parametrize("problem", ["missing_predictor", "no_ids", "no_rationale"])
def test_final_boundary_errors(journey, problem):
    _, _, final, run, models = journey
    rationale = "Approved"
    if problem == "missing_predictor":
        final = final.drop(columns="driver_age")
    elif problem == "no_ids":
        run = run.model_copy(update={"record_ids": ()})
    else:
        rationale = " "
    with pytest.raises(ValueError):
        evaluate_final(
            run,
            models,
            model="glm",
            df=final,
            final_test_ids=final.record_id.tolist(),
            rationale=rationale,
        )


def test_final_refit_handoff_cross_process_identity(journey, tmp_path):
    full, _, _, _, _ = journey
    run, models = evaluated(journey)
    save_run(run, models, tmp_path / "evaluated.pkl")
    full.to_parquet(tmp_path / "full.parquet")
    code = """
import sys
from pathlib import Path
import pandas as pd
from azoic import load_run, save_run, refit_production, export_production
root = Path(sys.argv[1])
run, models = load_run(root / 'evaluated.pkl')
production, fitted = refit_production(
    run, models, df=pd.read_parquet(root / 'full.parquet'), rationale='Approved')
save_run(production, fitted, root / 'production.pkl')
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
    code = """
import sys
from pathlib import Path
import pandas as pd
from azoic import load_run, export_production
root = Path(sys.argv[1])
run, models = load_run(root / 'production.pkl')
export_production(run, models, cases=pd.DataFrame({'driver_age': [30.], 'region': ['urban']}),
                  feature_units={'driver_age': 'years', 'region': 'category'}, out=root / 'bundle')
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_raw_typed_categorical_handoff_preserves_schema_and_rejects_unseen(journey, tmp_path):
    full, _, _, run, _ = journey
    full = full.copy()
    full["ordered_int"] = pd.Categorical(
        np.resize([2, 1, 3], len(full)), categories=[2, 1, 3], ordered=True
    )
    full["flag"] = pd.Categorical(
        np.resize([True, False], len(full)), categories=[True, False], ordered=True
    )
    config = run.config.model_copy(deep=True)
    config.preprocessing = None
    config.features = ["ordered_int", "flag", "vehicle_age"]
    run, models = run_experiment(config, df=full.iloc[:480], return_estimators=True)
    run = evaluate_final(
        run,
        models,
        model="glm",
        df=full.iloc[480:],
        final_test_ids=full.record_id.iloc[480:].tolist(),
        rationale="Selected",
    )
    production, fitted = refit_production(run, models, df=full, rationale="Approved")
    cases = pd.DataFrame(
        {
            "ordered_int": pd.Categorical([2, 1], categories=[2, 1, 3], ordered=True),
            "flag": pd.Categorical([True, False], categories=[True, False], ordered=True),
            "vehicle_age": [4.0, 6.0],
        }
    )
    units = {"ordered_int": "category", "flag": "category", "vehicle_age": "years"}
    for bad_cases in [cases.assign(ordered_int=True), cases.assign(flag=1)]:
        with pytest.raises(ValueError, match="supplied synthetic case cannot be scored"):
            export_production(
                production, fitted, cases=bad_cases, feature_units=units, out=tmp_path / "invalid"
            )
        assert not list(tmp_path.iterdir())

    path = export_production(
        production,
        fitted,
        cases=cases,
        feature_units=units,
        out=tmp_path / "bundle",
    )
    specification = json.loads(path.read_text())
    feature_schemas = {feature["name"]: feature for feature in specification["features"]}
    assert feature_schemas["ordered_int"]["categories"] == [2, 1, 3]
    assert feature_schemas["flag"]["categories"] == [True, False]
    assert feature_schemas["ordered_int"]["ordered"] is True
    agreements = json.loads((path.parent / "agreement.json").read_text())
    assert all(
        case["outcome"] == "rate" for case in agreements if case["case"].startswith("synthetic-")
    )
    assert all(
        case["outcome"] == "reject" for case in agreements if case["case"].endswith("-unseen")
    )
    result = subprocess.run(
        [sys.executable, str(path.parent / "score.py")], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
    # Record-oriented engines can supply scalar columns; the recipe restores the fitted schema.
    records = pd.DataFrame(cases.to_dict("records"))
    records.to_parquet(tmp_path / "inputs.parquet")
    result = subprocess.run(
        [
            sys.executable,
            str(path.parent / "score.py"),
            str(tmp_path / "inputs.parquet"),
            str(tmp_path / "rates.csv"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    np.testing.assert_allclose(
        pd.read_csv(tmp_path / "rates.csv").predicted_rate, fitted["glm"].predict(cases), rtol=1e-12
    )
    records["ordered_int"] = True
    records.to_parquet(tmp_path / "unseen.parquet")
    result = subprocess.run(
        [
            sys.executable,
            str(path.parent / "score.py"),
            str(tmp_path / "unseen.parquet"),
            str(tmp_path / "unseen.csv"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "unknown raw category for 'ordered_int'" in result.stderr
    assert not (tmp_path / "unseen.csv").exists()


@pytest.mark.parametrize("production_card", [False, True])
def test_final_cards_keep_protected_columns_under_experiment(journey, production_card):
    from azoic import model_card

    full, development, final, run, _ = journey
    config = run.config.model_copy(deep=True)
    config.spec.protected_cols = ["vehicle_brand"]
    run, models = run_experiment(config, df=development, return_estimators=True)
    run = evaluate_final(
        run,
        models,
        model="glm",
        df=final,
        final_test_ids=final.record_id.tolist(),
        rationale="Selected",
    )
    if production_card:
        run, _ = refit_production(run, models, df=full, rationale="Approved")
    card = model_card(run)
    experiment = card.split("## Experiment", 1)[1].split("\n## ", 1)[0]
    assert "- protected columns: `vehicle_brand`" in experiment
    assert card.count("- protected columns:") == 1
