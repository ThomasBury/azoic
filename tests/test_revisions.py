"""M59: fixed mappings, independent tariff revisions and saved-run/export agreement."""

import os
import re
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml
from sklearn.base import clone
from typer.testing import CliRunner

from azoic import (
    AutoBinner,
    AutoGrouper,
    DatasetSpec,
    ExperimentConfig,
    ModelSpec,
    PreprocessingSpec,
    RevisedTariff,
    apply_tariff,
    export_tariff,
    load_run,
    revise_run,
    revise_tariff,
    run_experiment,
    save_run,
)
from azoic.cli import app
from azoic.models import RiskGBM, RiskGLM
from azoic.reporting import comparison_dashboard, comparison_table, model_card
from tests.conftest import make_synthetic_portfolio


def test_dashboard_distinguishes_fitted_and_revised_rates(candidate, monkeypatch):
    go = pytest.importorskip("plotly.graph_objects")
    frame, run, estimators = candidate
    revised, _ = revise_run(run, estimators, model="glm", df=frame, replacements=[])
    captured = []

    def capture(figure, **kwargs):
        captured.append(figure)
        return "html"

    monkeypatch.setattr(go.Figure, "to_html", capture)
    assert comparison_dashboard([run, revised]) == "html"
    for trace in captured[0].data[1:]:
        assert list(trace.x) == [
            "fixed / glm",
            "fixed / gbm",
            "fixed / glm (revised)",
            "fixed / gbm",
        ]


def fixed_preprocessing(edge=25.0):
    return PreprocessingSpec(
        binner={
            "cols": ["driver_age"],
            "fixed": {"driver_age": {"edges": [edge, 60.0], "closure": "left", "missing": 1}},
        },
        grouper={
            "cols": ["region"],
            "fixed": {
                "region": {
                    "groups": [
                        {"level": "urban", "group": "metro"},
                        {"level": "suburban", "group": "metro"},
                        {"level": "rural", "group": "other"},
                    ],
                    "missing": "other",
                    "unseen": "metro",
                }
            },
        },
    )


@pytest.fixture
def candidate(tmp_path):
    frame = make_synthetic_portfolio(n=900).assign(record_id=np.arange(900))
    path = tmp_path / "development.parquet"
    frame.to_parquet(path)
    config = ExperimentConfig(
        name="fixed",
        data_path=str(path),
        features=["driver_age", "region"],
        spec=DatasetSpec(
            target="claim_amount",
            exposure="exposure",
            claim_count="claim_count",
            id_col="record_id",
        ),
        preprocessing=fixed_preprocessing(),
        models={
            "glm": ModelSpec(params={"family": "tweedie", "link": "log"}),
            "gbm": ModelSpec(kind="gbm", preprocess=False, params={"n_estimators": 5, "n_jobs": 1}),
        },
    )
    run, estimators = run_experiment(config, df=frame, return_estimators=True)
    return frame, run, estimators


@pytest.mark.parametrize("closure,expected", [("left", [0, 1, 1, 1]), ("right", [0, 0, 1, 1])])
def test_fixed_closure_clone_and_explicit_destinations(closure, expected):
    fixed = {"age": {"edges": [25.0], "closure": closure, "missing": 1}}
    transformer = AutoBinner(cols=["age"], fixed=fixed)
    cloned = clone(transformer)
    frame = pd.DataFrame(
        {"age": [np.nextafter(25.0, -np.inf), 25.0, np.nextafter(25.0, np.inf), np.nan]}
    )
    fitted = cloned.fit(frame)
    assert fitted.transform(frame).age.cat.codes.tolist() == expected
    assert not fitted.trees_
    assert fitted.closure_["age"] == closure
    assert transformer.fixed is fixed and not hasattr(transformer, "mapping_")
    fitted.set_mapping(fitted.mapping_)
    assert fitted.transform(frame).age.cat.codes.tolist() == expected


def test_fixed_typed_groups_and_distinct_missing_unseen():
    groups = [{"level": 1, "group": "integer"}, {"level": "1", "group": "string"}]
    frame = pd.DataFrame({"code": pd.Series([1, "1", None, "new"], dtype=object)})
    fitted = AutoGrouper(
        cols=["code"], fixed={"code": {"groups": groups, "missing": "integer", "unseen": "string"}}
    ).fit(frame)
    with pytest.warns(UserWarning, match="unseen"):
        assert fitted.transform(frame).code.tolist() == ["integer", "string", "integer", "string"]
    assert list(fitted.mapping_["code"]) == [1, "1"]
    original = deepcopy(fitted.fixed)
    cloned = clone(fitted).fit(frame)
    assert cloned.mapping_ == fitted.mapping_ and fitted.fixed == original


def test_freezing_quantile_mapping_preserves_separate_missing_bin():
    frame = pd.DataFrame({"age": [20.0, 25.0, 40.0, np.nan]})
    learned = AutoBinner(cols=["age"], strategy="quantile", max_bins=2).fit(frame)
    fixed = {
        "age": {
            "edges": learned.mapping_["age"].tolist(),
            "closure": learned.closure_["age"],
            "missing": learned.missing_["age"],
        }
    }
    frozen = AutoBinner(cols=["age"], fixed=fixed).fit(frame)
    pd.testing.assert_frame_equal(frozen.transform(frame), learned.transform(frame))
    assert frozen.transform(frame).age.iloc[-1] == "Missing"


@pytest.mark.parametrize(
    "fixed",
    [
        {"age": {"edges": [25.0, 25.0], "closure": "left", "missing": 0}},
        {"age": {"edges": [np.inf], "closure": "left", "missing": 0}},
        {"age": {"edges": [25.0], "closure": "left"}},
        {"age": {"edges": [25.0], "closure": "left", "missing": 3}},
        {"age": {"edges": [25.0], "closure": "both", "missing": 0}},
        {"unknown": {"edges": [25.0], "closure": "left", "missing": 0}},
    ],
)
def test_invalid_fixed_bins_fail_before_model_fit(fixed):
    with pytest.raises(ValueError):
        AutoBinner(cols=["age"], fixed=fixed).fit(pd.DataFrame({"age": [20.0, 30.0]}))


def test_yaml_mapping_edit_refits_new_candidate_and_preserves_original(candidate, tmp_path):
    frame, original, estimators = candidate
    before = estimators["glm"].predict(frame[original.feature_names])
    config = original.config.model_copy(deep=True)
    config.name = "age-revision"
    config.preprocessing = fixed_preprocessing(35.0)
    path = tmp_path / "revised.yaml"
    path.write_text(yaml.safe_dump(config.model_dump(mode="json")))
    python_run, python_models = run_experiment(config, df=frame, return_estimators=True)
    yaml_run, yaml_models = run_experiment(ExperimentConfig.from_yaml(path), return_estimators=True)
    assert yaml_run.train_indices == python_run.train_indices == original.train_indices
    assert yaml_run.config.preprocessing == python_run.config.preprocessing
    np.testing.assert_array_equal(
        yaml_models["glm"].predict(frame[original.feature_names]),
        python_models["glm"].predict(frame[original.feature_names]),
    )
    np.testing.assert_array_equal(estimators["glm"].predict(frame[original.feature_names]), before)
    assert estimators["glm"].named_steps["binner"].mapping_["driver_age"].tolist() == [25.0, 60.0]
    assert python_models["glm"].named_steps["binner"].mapping_["driver_age"].tolist() == [
        35.0,
        60.0,
    ]
    assert not np.array_equal(python_models["glm"].predict(frame[original.feature_names]), before)
    guide = (Path(__file__).parents[1] / "docs/guide/data-preprocessing.md").read_text()
    documented = next(
        block for block in re.findall(r"```yaml\n(.*?)```", guide, re.S) if "fixed:" in block
    )
    assert yaml.safe_load(documented)["preprocessing"] == fixed_preprocessing(30.0).model_dump()


def test_revision_calibration_saved_scoring_and_workbook_match(candidate, tmp_path, monkeypatch):
    frame, run, estimators = candidate
    before = estimators["glm"].predict(frame[run.feature_names])
    original_config = run.config.model_dump()

    def reject(*args, **kwargs):
        raise AssertionError("factor revisions must not fit")

    for cls in (RiskGLM, RiskGBM, AutoBinner, AutoGrouper):
        monkeypatch.setattr(cls, "fit", reject)
    changes = [
        {
            "feature": "region",
            "level": "metro",
            "factor": 1.4,
            "reason": "Approved technical adjustment",
        }
    ]
    revised_run, revised_models = revise_run(
        run, estimators, model="glm", replacements=changes, df=frame
    )
    revised = revised_models["glm"]
    assert isinstance(revised, RevisedTariff)
    assert run.config.model_dump() == original_config
    assert not run.models["glm"].revision
    assert revised_run.models["glm"].revision == revised.revision
    assert revised_run.train_indices == run.train_indices
    np.testing.assert_array_equal(estimators["glm"].predict(frame[run.feature_names]), before)
    train = frame.iloc[list(run.train_indices)]
    rates = revised.predict(frame[run.feature_names])
    assert np.dot(rates[list(run.train_indices)], train.exposure) == pytest.approx(
        train.claim_amount.sum()
    )
    cal = revised.revision["calibration"]
    assert cal["multiplier"] == pytest.approx(cal["observed_total"] / cal["predicted_total_before"])
    assert "revised" in model_card(revised_run)
    assert comparison_table([run, revised_run]).evidence.tolist() == [
        "development",
        "development",
        "development (revised tariff)",
        "development",
    ]
    out = tmp_path / "revised.xlsx"
    revised.source.distillation_metrics_ = {
        "teacher_student_deviance": 0.1,
        "student_teacher_total_ratio": 1.0,
    }
    export_tariff(revised, out, recalibrate=False)
    sheets = pd.read_excel(out, sheet_name=None)
    assert list(sheets) == ["base_rate", "factors", "mappings"]
    assert sheets["base_rate"].teacher_student_deviance.iloc[0] == 0.1
    workbook = deepcopy(revised.tariff)
    workbook["base_rate"] = sheets["base_rate"].base_rate.iloc[0]
    for row in sheets["factors"].itertuples():
        if row.feature in workbook["numeric"]:
            workbook["numeric"][row.feature] = np.log(row.multiplicative_factor)
        else:
            workbook["categorical"][row.feature][row.level] = row.multiplicative_factor
    transformed = revised.source[:-1].transform(frame[run.feature_names])
    np.testing.assert_allclose(apply_tariff(workbook, transformed), rates, rtol=1e-12)
    row = sheets["factors"].query("feature == 'region' and level == 'metro'").iloc[0]
    assert row.multiplicative_factor == 1.4 and row.reason == changes[0]["reason"]
    assert row.original_factor == revised.revision["changes"][0]["original_factor"]
    artifact = tmp_path / "revised.pkl"
    save_run(revised_run, revised_models, artifact)
    restored_run, restored_models = load_run(artifact)
    np.testing.assert_array_equal(restored_models["glm"].predict(frame[run.feature_names]), rates)
    assert restored_run.models["glm"].revision == revised.revision
    probe = tmp_path / "probe.parquet"
    frame[["record_id", *run.feature_names]].to_parquet(probe)
    for command in (
        [
            "predict",
            "--run",
            str(artifact),
            "--model",
            "glm",
            "--data",
            str(probe),
            "--out",
            str(tmp_path / "rates.csv"),
        ],
        [
            "export-tariff",
            "--run",
            str(artifact),
            "--model",
            "glm",
            "--no-recalibrate",
            "--out",
            str(tmp_path / "cli.xlsx"),
        ],
    ):
        result = CliRunner().invoke(app, command)
        assert result.exit_code == 0, (result.output, result.exception)
    np.testing.assert_allclose(pd.read_csv(tmp_path / "rates.csv").predicted_rate, rates)
    code = """
import numpy as np
import pandas as pd
from azoic import load_run
run, models = load_run('revised.pkl')
np.save('fresh.npy', models['glm'].predict(pd.read_parquet('probe.parquet')[run.feature_names]))
"""
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[1] / "src")}
    process = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert process.returncode == 0, process.stderr
    np.testing.assert_array_equal(np.load(tmp_path / "fresh.npy"), rates)
    zero = revise_tariff(revised, [], X=train, y=np.zeros(len(train)), exposure_col="exposure")
    np.testing.assert_array_equal(zero.predict(frame[run.feature_names]), np.zeros(len(frame)))
    twice = revise_tariff(zero, [], X=train, y=train.claim_amount, exposure_col="exposure")
    np.testing.assert_array_equal(twice.predict(frame[run.feature_names]), rates)


@pytest.mark.parametrize(
    "change",
    [
        {"feature": "region", "level": "metro", "factor": 0, "reason": "zero"},
        {"feature": "region", "level": "metro", "factor": np.inf, "reason": "invalid"},
        {"feature": "region", "level": "metro", "factor": 1.2, "reason": " "},
        {"feature": "region", "level": 1, "factor": 1.2, "reason": "unknown level"},
    ],
)
def test_failed_revisions_preserve_original_and_workbook(candidate, tmp_path, change):
    frame, run, estimators = candidate
    before = estimators["glm"].predict(frame[run.feature_names])
    out = tmp_path / "existing.xlsx"
    export_tariff(estimators["glm"], out, recalibrate=False)
    contents = out.read_bytes()
    with pytest.raises(ValueError):
        revised_run, revised_models = revise_run(
            run, estimators, model="glm", replacements=[change], df=frame
        )
        export_tariff(revised_models["glm"], out, recalibrate=False)
    assert out.read_bytes() == contents
    np.testing.assert_array_equal(estimators["glm"].predict(frame[run.feature_names]), before)
    with pytest.raises(ValueError, match="fingerprint"):
        revise_run(run, estimators, model="glm", replacements=[], df=frame.iloc[::-1])


@pytest.mark.parametrize(
    "spec",
    [
        {"groups": [{"level": 1, "group": "A"}]},
        {
            "groups": [{"level": 1, "group": "A"}, {"level": True, "group": "B"}],
            "missing": "A",
            "unseen": "B",
        },
        {"groups": [{"level": 1, "group": True}], "missing": 1, "unseen": True},
        {"groups": [{"level": None, "group": "A"}], "missing": "A", "unseen": "A"},
    ],
)
def test_invalid_fixed_groups_reject_ambiguous_types_and_missing_routes(spec):
    with pytest.raises(ValueError):
        AutoGrouper(cols=["code"], fixed={"code": spec}).fit(pd.DataFrame({"code": [1, 2]}))


def test_fixed_group_setter_keeps_valid_destinations():
    frame = pd.DataFrame({"code": ["a", "b", None, "new"]})
    grouper = AutoGrouper(
        cols=["code"],
        fixed={
            "code": {
                "groups": [{"level": "a", "group": "A"}, {"level": "b", "group": "B"}],
                "missing": "A",
                "unseen": "B",
            }
        },
    ).fit(frame)
    grouper.set_mapping(grouper.mapping_)
    with pytest.warns(UserWarning, match="unseen"):
        assert grouper.transform(frame).code.tolist() == ["A", "B", "A", "B"]
    grouper.set_mapping({"code": {"a": "C", "b": "D"}}, missing={"code": "D"})
    with pytest.warns(UserWarning, match="unseen"):
        assert grouper.transform(frame).code.tolist() == ["C", "D", "D", "D"]


def test_repeated_factor_edits_and_failed_export_preserve_sources(candidate, tmp_path, monkeypatch):
    frame, run, estimators = candidate
    first_run, first_models = revise_run(
        run,
        estimators,
        model="glm",
        df=frame,
        replacements=[
            {"feature": "region", "level": "metro", "factor": 1.4, "reason": "first decision"}
        ],
    )
    second_run, second_models = revise_run(
        first_run,
        first_models,
        model="glm",
        df=frame,
        replacements=[
            {"feature": "region", "level": "metro", "factor": 1.1, "reason": "second decision"}
        ],
    )
    second = second_models["glm"]
    assert second.revision["changes"][1]["original_factor"] == 1.4
    out = tmp_path / "revised.xlsx"
    export_tariff(second, out, recalibrate=False)
    row = (
        pd.read_excel(out, sheet_name="factors")
        .query("feature == 'region' and level == 'metro'")
        .iloc[0]
    )
    assert row.original_factor == first_models["glm"].revision["changes"][0]["original_factor"]
    assert row.reason == "first decision; second decision"
    before = out.read_bytes()
    rates = first_models["glm"].predict(frame[run.feature_names])
    with pytest.raises(ValueError, match="revision evidence"):
        save_run(run, second_models, tmp_path / "mismatched.pkl")
    with pytest.raises(ValueError, match="already record"):
        export_tariff(second, out)
    assert out.read_bytes() == before

    original_write = pd.DataFrame.to_excel

    def fail(self, *args, **kwargs):
        if kwargs.get("sheet_name") == "factors":
            raise OSError("simulated failed workbook write")
        return original_write(self, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "to_excel", fail)
    with pytest.raises(OSError, match="simulated"):
        export_tariff(second, out, recalibrate=False)
    assert out.read_bytes() == before
    np.testing.assert_array_equal(first_models["glm"].predict(frame[run.feature_names]), rates)


def test_tuned_fixed_mappings_and_typed_numeric_factors(candidate):
    pytest.importorskip("optuna")
    from azoic.tune import tune_experiment

    frame, run, _ = candidate
    config = run.config.model_copy(update={"models": {"glm": run.config.models["glm"]}})
    tuned = tune_experiment(config, df=frame, n_trials=1, return_estimators=True)
    np.testing.assert_array_equal(
        tuned.estimators["glm"].named_steps["binner"].mapping_["driver_age"], [25.0, 60.0]
    )
    revised_run, _ = revise_run(
        tuned.run, tuned.estimators, model="glm", df=frame, replacements=[], recalibrate=False
    )
    assert revised_run.tuning_settings == tuned.run.tuning_settings
    assert revised_run.runtime_versions == tuned.run.runtime_versions
    X = pd.DataFrame(
        {"code": pd.Categorical([1, 2] * 20), "age": np.arange(40) / 40, "exposure": 1.0}
    )
    model = RiskGLM(family="poisson", link="log", exposure_col="exposure").fit(
        X, np.where(X.code == 1, 2.0, 4.0)
    )
    revised = revise_tariff(
        model,
        [
            {"feature": "code", "level": 1, "factor": 1.2, "reason": "typed reference change"},
            {"feature": "age", "level": "_per_unit", "factor": 1.01, "reason": "numeric change"},
        ],
        recalibrate=False,
    )
    assert revised.tariff["categorical"]["code"][1] == 1.2
    assert np.isfinite(revised.predict(X)).all()
    with pytest.raises(ValueError, match="typed"):
        revise_tariff(
            model,
            [{"feature": "code", "level": "1", "factor": 1.2, "reason": "wrong type"}],
            recalibrate=False,
        )


def test_revision_calibration_cannot_use_development_validation_outcomes(candidate):
    frame, run, estimators = candidate
    changed = frame.copy()
    column = changed.columns.get_loc("claim_amount")
    changed.iloc[list(run.test_indices), column] *= 10
    other_run, other_models = run_experiment(run.config, df=changed, return_estimators=True)
    change = [{"feature": "region", "level": "metro", "factor": 1.3, "reason": "same decision"}]
    first, first_models = revise_run(run, estimators, model="glm", df=frame, replacements=change)
    second, second_models = revise_run(
        other_run, other_models, model="glm", df=changed, replacements=change
    )
    assert (
        first.models["glm"].revision["calibration"] == second.models["glm"].revision["calibration"]
    )
    np.testing.assert_array_equal(
        first_models["glm"].predict(frame[run.feature_names]),
        second_models["glm"].predict(frame[run.feature_names]),
    )
    assert (
        first.models["glm"].metrics["op_ratio_test"]
        != second.models["glm"].metrics["op_ratio_test"]
    )
