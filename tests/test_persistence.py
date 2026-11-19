"""Saved candidates retain fitted state; consuming them never trains."""

import os
import pickle
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml
from typer.testing import CliRunner

from azoic import (
    DatasetSpec,
    ExperimentConfig,
    ModelSpec,
    evaluate_final,
    load_run,
    refit_production,
    revise_run,
    run_experiment,
    save_run,
)
from azoic.cli import app
from azoic.models import FrequencySeverityModel, RiskGBM, RiskGLM
from azoic.preprocessing import AutoBinner, AutoGrouper
from azoic.workflow import PreprocessingSpec
from tests.conftest import make_synthetic_portfolio

runner = CliRunner()


@pytest.fixture
def candidates(tmp_path):
    frame = make_synthetic_portfolio(n=800).assign(record_id=np.arange(800))
    frame["private_note"] = [f"excluded-row-note-{i}" for i in range(len(frame))]
    path = tmp_path / "development.parquet"
    frame.to_parquet(path)
    config = ExperimentConfig(
        data_path=str(path),
        spec=DatasetSpec(
            target="claim_amount",
            exposure="exposure",
            claim_count="claim_count",
            id_col="record_id",
            excluded_cols=["private_note"],
            currency="EUR",
        ),
        features=["driver_age", "region"],
        preprocessing=PreprocessingSpec(
            binner={"cols": ["driver_age"], "max_bins": 3},
            grouper={"cols": ["region"], "max_groups": 2},
        ),
        models={
            "glm": ModelSpec(params={"family": "tweedie", "link": "log"}),
            "gbm": ModelSpec(kind="gbm", preprocess=False, params={"n_estimators": 5, "n_jobs": 1}),
            "gbm-pipeline": ModelSpec(kind="gbm", params={"n_estimators": 5, "n_jobs": 1}),
            "fsm": ModelSpec(
                kind="frequency_severity",
                frequency=ModelSpec(params={"family": "poisson", "link": "log"}),
                severity=ModelSpec(params={"family": "gamma", "link": "log"}),
            ),
        },
    )
    run, estimators = run_experiment(config, df=frame, return_estimators=True)
    artifact = tmp_path / "candidates.pkl"
    save_run(run, estimators, artifact)
    return frame, path, run, estimators, artifact


def reject_fit(*args, **kwargs):
    raise AssertionError("saved-run operations must never fit")


def test_fresh_process_exact_predictions_and_mapping_fidelity(candidates, tmp_path):
    frame, path, run, estimators, artifact = candidates
    probe = frame[run.feature_names].iloc[:30].copy()
    edges = estimators["glm"].named_steps["binner"].mapping_["driver_age"]
    boundaries = edges[np.isfinite(edges)]
    assert boundaries.size > 0
    # Exercise learned <= edges and adjacent floats, as well as native missing routing.
    values = np.concatenate(
        [
            boundaries,
            np.nextafter(boundaries, -np.inf),
            np.nextafter(boundaries, np.inf),
            [np.nan],
        ]
    )
    probe["driver_age"] = probe.driver_age.astype(float)
    probe.iloc[: len(values), 0] = values
    probe.loc[probe.index[-1], "region"] = "previously-unseen"
    probe.to_parquet(tmp_path / "probe.parquet")
    expected = {name: est.predict(probe) for name, est in estimators.items()}
    copied = deepcopy(estimators)
    copied["glm"].named_steps["model"].backend_._align_info_logs_emitted = {"test cache entry"}
    save_run(run, copied, artifact)
    code = """
import numpy as np
import pandas as pd
from azoic import load_run
from azoic.models import RiskGLM, RiskGBM, FrequencySeverityModel
from azoic.preprocessing import AutoBinner, AutoGrouper
def reject(*args, **kwargs):
    raise AssertionError('reload must not fit')
for cls in (RiskGLM, RiskGBM, FrequencySeverityModel, AutoBinner, AutoGrouper):
    cls.fit = reject
run, estimators = load_run('candidates.pkl')
probe = pd.read_parquet('probe.parquet')
np.savez('predictions.npz', **{name: est.predict(probe) for name, est in estimators.items()})
"""
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[1] / "src")}
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    with np.load(tmp_path / "predictions.npz") as actual:
        for name in expected:
            np.testing.assert_array_equal(actual[name], expected[name])
    restored, fitted = load_run(artifact)
    assert restored.config == run.config
    assert restored.record_ids == tuple(frame.record_id)
    assert restored.train_indices == run.train_indices
    assert restored.test_indices == run.test_indices
    assert restored.data_fingerprint == run.data_fingerprint
    assert restored.runtime_versions == run.runtime_versions
    for step in ("binner", "grouper"):
        original = estimators["glm"].named_steps[step]
        reloaded = fitted["glm"].named_steps[step]
        inputs = frame[list(original.feature_names_in_)]
        pd.testing.assert_frame_equal(original.transform(inputs), reloaded.transform(inputs))
    # The envelope contains only summaries and estimators, with no supplied row frame.
    with artifact.open("rb") as stream:
        assert set(pickle.load(stream)) == {"format", "run", "estimators"}
    assert b"excluded-row-note-" not in artifact.read_bytes()
    path.unlink()
    load_run(artifact)  # Reload does not dereference config.data_path.


def test_saved_cli_consumers_do_not_fit(candidates, tmp_path, monkeypatch):
    frame, path, run, estimators, artifact = candidates
    for cls in (RiskGLM, RiskGBM, FrequencySeverityModel, AutoBinner, AutoGrouper):
        monkeypatch.setattr(cls, "fit", reject_fit)
    monkeypatch.setattr("azoic.cli.run_experiment", reject_fit)
    probe = tmp_path / "predictors.parquet"
    frame[["record_id", *run.feature_names]].to_parquet(probe)
    predictions = tmp_path / "rates.csv"
    commands = [
        ["compare", "--run", str(artifact), "--run", str(artifact)],
        ["report", "--run", str(artifact), "--out", str(tmp_path / "card.md")],
        [
            "predict",
            "--run",
            str(artifact),
            "--model",
            "glm",
            "--data",
            str(probe),
            "--out",
            str(predictions),
        ],
    ]
    for recalibrate in (False, True):
        commands.append(
            [
                "export-tariff",
                "--run",
                str(artifact),
                "--model",
                "glm",
                "--out",
                str(tmp_path / f"tariff-{recalibrate}.xlsx"),
                *(["--data", str(path)] if recalibrate else ["--no-recalibrate"]),
            ]
        )
    for command in commands:
        result = runner.invoke(app, command)
        assert result.exit_code == 0, (result.output, result.exception)
    actual = pd.read_csv(predictions)
    assert actual.record_id.tolist() == frame.record_id.tolist()
    np.testing.assert_allclose(
        actual.predicted_rate, estimators["glm"].predict(frame[run.feature_names])
    )
    assert "development" in (tmp_path / "card.md").read_text()
    raw = pd.read_excel(tmp_path / "tariff-False.xlsx", sheet_name="base_rate").iloc[0]
    calibrated = pd.read_excel(tmp_path / "tariff-True.xlsx", sheet_name="base_rate").iloc[0]
    train = frame.iloc[list(run.train_indices)]
    multiplier = train.claim_amount.sum() / np.dot(
        estimators["glm"].predict(train[run.feature_names]), train.exposure
    )
    assert calibrated.base_rate / raw.base_rate == pytest.approx(multiplier)
    before = (tmp_path / "tariff-True.xlsx").read_bytes()
    for changed in (frame.iloc[::-1], frame.assign(claim_amount=frame.claim_amount * 2)):
        changed.to_parquet(path)
        result = runner.invoke(app, commands[-1])
        assert result.exit_code != 0 and "fingerprint" in result.output
        assert (tmp_path / "tariff-True.xlsx").read_bytes() == before
    for options in (["--distill"], []):
        result = runner.invoke(
            app,
            [
                "export-tariff",
                "--run",
                str(artifact),
                "--model",
                "glm",
                "--out",
                str(tmp_path / "no.xlsx"),
                *options,
            ],
        )
        assert result.exit_code != 0
    assert not (tmp_path / "no.xlsx").exists()


def test_save_failure_preserves_destination_and_permissions(candidates, monkeypatch):
    _, _, run, estimators, artifact = candidates
    artifact.chmod(0o640)
    save_run(run, estimators, artifact)
    assert artifact.stat().st_mode & 0o777 == 0o640
    before = artifact.read_bytes()
    files = set(artifact.parent.iterdir())

    def broken_dump(obj, stream, **kwargs):
        stream.write(b"partial")
        raise OSError("disk full")

    monkeypatch.setattr("azoic.workflow.pickle.dump", broken_dump)
    with pytest.raises(OSError, match="disk full"):
        save_run(run, estimators, artifact)
    assert artifact.read_bytes() == before
    assert set(artifact.parent.iterdir()) == files
    with pytest.raises(ValueError, match="names"):
        save_run(run, {}, artifact)
    assert artifact.read_bytes() == before


def test_load_rejects_unknown_format_and_mismatched_environment(candidates):
    _, _, run, _, artifact = candidates
    with artifact.open("rb") as stream:
        envelope = pickle.load(stream)
    envelope["run"] = run.model_copy(update={"runtime_versions": {"python": "0.0.0"}})
    artifact.write_bytes(pickle.dumps(envelope))
    with pytest.raises(ValueError, match="environment mismatch for python"):
        load_run(artifact)
    artifact.write_bytes(pickle.dumps({"format": "future"}))
    with pytest.raises(ValueError, match="supported format"):
        load_run(artifact)


def test_same_name_swap_fails_before_scoring_or_replacing_artifact(
    candidates, tmp_path, monkeypatch
):
    frame, _, run, estimators, artifact = candidates
    final = frame.head(60).assign(record_id=np.arange(800, 860))
    final_args = {
        "model": "glm",
        "df": final,
        "final_test_ids": final.record_id.tolist(),
        "rationale": "Frozen",
    }
    evaluated = evaluate_final(run, estimators, **final_args)
    config = run.config.model_copy(update={"models": {"gbm": run.config.models["gbm"]}})
    _, alternate = run_experiment(
        config, df=frame.assign(claim_amount=2 * frame.claim_amount), return_estimators=True
    )
    swapped = {**estimators, **alternate}
    artifact.chmod(0o640)
    before = artifact.read_bytes()
    monkeypatch.setattr(RiskGLM, "predict", reject_fit)
    for operation in (
        lambda: save_run(run, swapped, artifact),
        lambda: evaluate_final(run, swapped, **final_args),
        lambda: revise_run(run, swapped, model="glm", df=frame, replacements=[]),
        lambda: refit_production(
            evaluated, swapped, df=pd.concat([frame, final]), rationale="Approved"
        ),
    ):
        with pytest.raises(ValueError, match="candidate 'gbm' fitted state"):
            operation()
    assert artifact.read_bytes() == before
    assert artifact.stat().st_mode & 0o777 == 0o640
    wrong_pair = tmp_path / "swapped.pkl"
    envelope = pickle.loads(before)
    envelope["estimators"] = swapped
    wrong_pair.write_bytes(pickle.dumps(envelope, protocol=5))
    with pytest.raises(ValueError, match="candidate 'gbm' fitted state"):
        load_run(wrong_pair)


def test_legacy_saved_run_requires_original_environment(candidates):
    _, _, run, estimators, artifact = candidates
    envelope = pickle.loads(artifact.read_bytes())
    del envelope["run"]._fitted_fingerprints
    artifact.write_bytes(pickle.dumps(envelope, protocol=5))
    with pytest.raises(ValueError, match="no complete recorded fitted identities"):
        load_run(artifact)
    legacy = envelope["run"]
    with pytest.raises(ValueError, match="original trusted environment"):
        save_run(legacy, estimators, artifact)
    assert not hasattr(legacy, "_fitted_fingerprints")
    assert set(run.model_dump()) == set(legacy.model_dump())


def test_fit_and_tune_cli_save_selected_candidates(candidates, tmp_path, monkeypatch):
    pytest.importorskip("optuna")
    _, _, run, _, _ = candidates
    config = run.config.model_copy(update={"models": {"glm": run.config.models["glm"]}})
    cfg_path = tmp_path / "experiment.yaml"
    cfg_path.write_text(yaml.safe_dump(config.model_dump(mode="json")))
    for command in ("fit", "tune"):
        artifact = tmp_path / f"{command}.pkl"
        best = tmp_path / "selected.yaml"
        result = runner.invoke(
            app,
            [
                command,
                "--config",
                str(cfg_path),
                "--save-run",
                str(artifact),
                "--quiet",
                *(["--trials", "1", "--best-config", str(best)] if command == "tune" else []),
            ],
        )
        assert result.exit_code == 0, (result.output, result.exception)
        saved, fitted = load_run(artifact)
        if command == "tune":
            selected = ExperimentConfig.from_yaml(best)
            assert selected == saved.config
            assert saved.tuning_settings["n_trials"] == 1
            fitted = deepcopy(fitted)
            fitted["glm"].predict(pd.read_parquet(config.data_path)[config.features])
            save_run(saved, fitted, artifact)
        code = """
import sys
import numpy as np
import pandas as pd
from azoic import load_run
from azoic.models import RiskGLM
def reject(*args, **kwargs):
    raise AssertionError('reload must not fit')
RiskGLM.fit = reject
run, fitted = load_run(sys.argv[1])
frame = pd.read_parquet(run.config.data_path)[run.feature_names]
np.save(sys.argv[2], fitted['glm'].predict(frame))
"""
        prediction_file = tmp_path / f"{command}-fresh.npy"
        result = subprocess.run(
            [sys.executable, "-c", code, str(artifact), str(prediction_file)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr
        np.testing.assert_array_equal(
            np.load(prediction_file),
            fitted["glm"].predict(pd.read_parquet(config.data_path)[config.features]),
        )
        for cls in (RiskGLM, AutoBinner, AutoGrouper):
            with monkeypatch.context() as context:
                context.setattr(cls, "fit", reject_fit)
                loaded, models = load_run(artifact)
                frame = pd.read_parquet(config.data_path)[config.features]
                np.testing.assert_array_equal(
                    models["glm"].predict(frame), fitted["glm"].predict(frame)
                )
