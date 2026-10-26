"""Runtime-only check: copy outside the checkout and run against each installed artifact."""

import subprocess
import sys
import tempfile
import warnings
from importlib import import_module
from importlib.metadata import distribution
from pathlib import Path
from unittest import TestCase

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.dummy import DummyRegressor
from sklearn.model_selection import KFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer

import azoic
from azoic import FrequencySeverityModel, op_ratio
from azoic.models import RiskGBM, RiskGLM
from azoic.preprocessing import AutoBinner, AutoGrouper
from azoic.reporting import model_card

package_path = Path(azoic.__file__).resolve()
installed = distribution("azoic")
assert package_path == Path(installed.locate_file("azoic/__init__.py")).resolve(), package_path
assert azoic.__version__ == installed.version
assert int(pd.__version__.split(".")[0]) >= 3
for module in (
    "data",
    "profile",
    "preprocessing",
    "models",
    "metrics",
    "validation",
    "plots",
    "tariff",
    "workflow",
    "reporting",
    "mlops",
    "tune",
    "cli",
):
    imported = import_module(f"azoic.{module}")
    assert Path(imported.__file__).resolve().parent == package_path.parent

for dtype in ("str", "string", "object"):
    X = pd.DataFrame({"x": np.tile(np.arange(20), 20) / 20})
    X["segment"] = pd.Series(["low", "high"] * 200, dtype=dtype)
    X["exposure"] = 1.0
    y = np.where(X["segment"] == "high", 60.0, 10.0) * np.exp(0.1 * X["x"])
    original = X.copy(deep=True)
    for model in (
        RiskGLM(family="tweedie", link="log", exposure_col="exposure"),
        RiskGBM(exposure_col="exposure", n_estimators=60, n_jobs=1),
    ):
        model.fit(X, y)
        assert np.isfinite(model.predict(X)).all()
        score = model.score(X, y)
        assert np.isfinite(score) and score > 0.8
        probe = X.iloc[:2].copy()
        probe["x"] = 0.5
        low, high = model.predict(probe)
        assert high > 2 * low
        pd.testing.assert_frame_equal(X, original)

print(f"azoic {azoic.__version__}; pandas {pd.__version__}; installed at {package_path}")
print("GLM/GBM fit, score, categorical influence, imports, and version checks passed")

checks = TestCase()

# Public development boundary works with runtime dependencies only.
portfolio = pd.DataFrame(
    {
        "id": ["a", "b", "c", "d"],
        "x": [1.0, 2.0, 3.0, 4.0],
        "exposure": 1.0,
        "amount": [0.0, 10.0, 20.0, np.nan],
    }
)
development, final_test = azoic.split_portfolio(portfolio, ["d"], id_col="id")
config = azoic.ExperimentConfig(
    data_path="not-read.parquet",
    features=["x"],
    spec=azoic.DatasetSpec(target="amount", exposure="exposure", id_col="id", currency="EUR"),
    models={"glm": azoic.ModelSpec(params={"family": "tweedie", "link": "log"})},
    preprocessing=azoic.PreprocessingSpec(
        binner={"cols": ["x"], "fixed": {"x": {"edges": [1.5], "closure": "left", "missing": 0}}}
    ),
)
summary = azoic.check_experiment(config, df=development)
assert summary["n_rows"] == 3 and summary["evidence"] == "development"
assert summary["portfolio_basis"]["currency"] == "EUR"
assert final_test.id.tolist() == ["d"] and final_test.amount.isna().all()

# Saved candidates score in a fresh installed process without fitting or source data.
run, estimators = azoic.run_experiment(config, df=development, return_estimators=True)
with tempfile.TemporaryDirectory() as folder:
    directory = Path(folder)
    azoic.save_run(run, estimators, directory / "run.pkl")
    revised_run, revised_models = azoic.revise_run(
        run,
        estimators,
        model="glm",
        df=development,
        replacements=[
            {
                "feature": "x",
                "level": "[1.5, inf)",
                "factor": 1.1,
                "reason": "synthetic installed revision check",
            }
        ],
    )
    azoic.save_run(revised_run, revised_models, directory / "revised.pkl")
    development.to_parquet(directory / "development.parquet")
    development[["id"]].assign(old_rate=10.0).iloc[::-1].to_parquet(directory / "incumbent.parquet")
    development[["id", "x"]].to_parquet(directory / "predictors.parquet")
    expected = estimators["glm"].predict(development[["x"]])
    revised_expected = revised_models["glm"].predict(development[["x"]])
    code = """
import numpy as np
import pandas as pd
from azoic import load_run
from azoic.models import RiskGLM, RiskGBM
from azoic.preprocessing import AutoBinner, AutoGrouper
def reject(*args, **kwargs):
    raise AssertionError('saved candidates must not fit')
for cls in (RiskGLM, RiskGBM, AutoBinner, AutoGrouper):
    cls.fit = reject
run, estimators = load_run('run.pkl')
np.save('rates.npy', estimators['glm'].predict(pd.read_parquet('predictors.parquet')[['x']]))
revised_run, revised_models = load_run('revised.pkl')
probe = pd.read_parquet('predictors.parquet')[['x']]
np.save('revised-rates.npy', revised_models['glm'].predict(probe))
from azoic.cli import app
from typer.testing import CliRunner
for command in (
    ['compare', '--run', 'run.pkl'],
    ['report', '--run', 'run.pkl'],
    ['predict', '--run', 'run.pkl', '--model', 'glm', '--data', 'predictors.parquet',
     '--out', 'rates.csv'],
    ['export-tariff', '--run', 'run.pkl', '--model', 'glm', '--no-recalibrate',
     '--out', 'tariff.xlsx'],
    ['report', '--run', 'revised.pkl'],
    ['report', '--review', '--run', 'run.pkl', '--run', 'revised.pkl',
     '--data', 'development.parquet', '--incumbent', 'incumbent.parquet',
     '--incumbent-rate', 'old_rate', '--selected', 'revised/glm',
     '--rationale', 'Synthetic installed review', '--out', 'review'],
    ['export-tariff', '--run', 'revised.pkl', '--model', 'glm', '--no-recalibrate',
     '--out', 'revised.xlsx'],
):
    result = CliRunner().invoke(app, command)
    assert result.exit_code == 0, (result.output, result.exception)
"""
    subprocess.run([sys.executable, "-c", code], cwd=directory, check=True)
    evidence = pd.read_csv(directory / "review" / "records.csv")
    for label, rates in (("run/glm", expected), ("revised/glm", revised_expected)):
        np.testing.assert_allclose(evidence.loc[evidence.candidate == label, "rate"], rates)
    assert (directory / "review" / "review.md").exists()
    np.testing.assert_array_equal(np.load(directory / "rates.npy"), expected)
    np.testing.assert_array_equal(np.load(directory / "revised-rates.npy"), revised_expected)
print("Saved-run persistence, fresh-process equality and no-fit CLI consumers passed")
for cls in (AutoBinner, AutoGrouper):
    kwargs = {"strategy": "tree"} if cls is AutoBinner else {}
    for value in (np.nan, np.inf, -np.inf, "nan", "inf", "-inf"):
        for source in ("y", "target_col"):
            frame = pd.DataFrame({"x": [0.0, 1.0, 2.0, 3.0]})
            outcomes = [value, 1.0, 2.0, 3.0]
            target_kwargs = {}
            if source == "target_col":
                frame["amount"] = outcomes
                target_kwargs["target_col"] = "amount"
                outcomes = None
            with checks.assertRaisesRegex(ValueError, "NaN|infinity"):
                cls(cols=["x"], **kwargs, **target_kwargs).fit(frame, outcomes)
    frame = pd.DataFrame({"age": [10.0, 20.0, 30.0, 40.0]})
    for fit_dataframe in (True, False):
        train, probe = (frame, frame.to_numpy()) if fit_dataframe else (frame.to_numpy(), frame)
        column = "age" if fit_dataframe else "x0"
        transformer = cls(cols=[column], **kwargs).fit(train, [1.0, 1.0, 9.0, 9.0])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with checks.assertRaisesRegex(ValueError, "missing fitted mapping columns"):
                transformer.transform(probe)
for direction in ("increasing", "decreasing"):
    frame = pd.DataFrame({"x": [5.0] * 4 + [np.nan]})
    binner = AutoBinner(cols=["x"], strategy="quantile", max_bins=4, monotonic=direction).fit(
        frame, [1.0, 1.0, 2.0, 2.0, 100.0]
    )
    assert binner.mapping_["x"].size == 0
    assert binner.transform(frame)["x"].cat.codes.tolist() == [0, 0, 0, 0, 1]
for cls in (AutoBinner, AutoGrouper):
    frame = pd.DataFrame({"x": [10.0, 20.0, 30.0, 40.0, np.nan], "e": 1.0})
    transformer = cls(cols=["x"], exposure_col="e").fit(frame, [1.0, 1.0, 10.0, 10.0, 10.0])
    expected = transformer.transform(frame)
    assert expected["x"].nunique() >= 2
    assert not expected["x"].isna().any()
    transformer.set_mapping(transformer.mapping_)
    pd.testing.assert_frame_equal(expected, transformer.transform(frame))
    assert transformer.missing_["x"] is not None
for command in (
    "check",
    "profile",
    "fit",
    "compare",
    "report",
    "predict",
    "export-tariff",
    "tune",
    "evaluate-final",
    "refit-production",
    "export-production",
):
    for entrypoint in (["azoic"], [sys.executable, "-m", "azoic.cli"]):
        result = subprocess.run(
            [*entrypoint, command, "--help"], check=True, capture_output=True, text=True
        )
        assert "Usage:" in result.stdout, (entrypoint, command)
print("Preprocessing contracts, constant bins and all eleven CLI helps (script/module) passed")

# Public, runtime-only composition recipe; also published in the compatibility guide.
X = pd.DataFrame(
    {
        "constant": [1.0, 1.0, 1.0],
        "exposure": [1.0, 3.0, 2.0],
        "claim_count": [1, 2, 0],
        "claim_amount": [10.0, 60.0, 0.0],
    }
)
original = X.copy(deep=True)
freq, sev = DummyRegressor(), DummyRegressor()
model = FrequencySeverityModel(freq=freq, sev=sev)
assert model.get_params()["freq__strategy"] == "mean"
model.set_params(freq__strategy="mean", sev__strategy="mean")
assert model.fit(X) is model
assert not hasattr(freq, "constant_") and not hasattr(sev, "constant_")
assert not hasattr(clone(model), "freq_")

# Independent weighted means: frequency = 3/6; severity = 70/3.
np.testing.assert_allclose(model.freq_.predict(X[["constant"]]), 0.5)
np.testing.assert_allclose(model.sev_.predict(X[["constant"]]), 70 / 3)
prediction = model.predict(X[["constant"]])
assert prediction.shape == (3,) and np.isfinite(prediction).all()
np.testing.assert_allclose(prediction, 35 / 3)
np.testing.assert_allclose(np.dot(prediction, X.exposure), 70)
np.testing.assert_allclose(op_ratio(X.claim_amount, prediction, X.exposure), 1)

pipeline = Pipeline(
    [
        ("identity", FunctionTransformer()),
        ("model", clone(model)),
    ]
)
assert pipeline.fit(X) is pipeline
np.testing.assert_allclose(pipeline.predict(X), prediction)
repeated = pd.concat([X, X], ignore_index=True)
scores = cross_val_score(pipeline, repeated, repeated.claim_amount / repeated.exposure, cv=KFold(2))
assert scores.shape == (2,) and np.isfinite(scores).all()
pd.testing.assert_frame_equal(X, original)

assert (package_path.parent / "py.typed").is_file()
print("Public component composition, cloning, nested parameters, pipeline and CV passed")


# Final-run provenance uses runtime dependencies only, with no optional integration imports.
config = azoic.ExperimentConfig(
    data_path="unused.parquet",
    spec=azoic.DatasetSpec(target="claim_amount", exposure="exposure", claim_count="claim_count"),
    features=["constant"],
    split="random",
    test_size=0.25,
    models={"glm": azoic.ModelSpec(params={"family": "poisson", "link": "log", "alpha": 0.0})},
)
run = azoic.run_experiment(config, df=repeated)
assert run.models["glm"].resolved_params["class"] == "azoic.models.RiskGLM"
assert run.models["glm"].resolved_params["max_iter"] == 100
assert run.models["glm"].resolved_params["exposure_col"] == "exposure"
assert "max_iter" not in run.models["glm"].params
assert run.runtime_versions["azoic"] == installed.version
assert run.runtime_versions["scikit-learn"] == distribution("scikit-learn").version
assert "python" in run.runtime_versions and "optuna" not in run.runtime_versions
assert run.tuning_settings == {}
assert "runtime versions:" in model_card(run)
assert "settings in `resolved_params`" in model_card(run)
print("Final-run constructor/runtime provenance and compact card passed")


# Final evaluation and production handoff work from installed runtime dependencies only.
full = pd.DataFrame(
    {
        "id": np.arange(80),
        "x": np.tile(np.arange(8), 10).astype(float),
        "e": 1.0,
        "amount": np.tile([0.0, 10.0, 20.0, 0.0, 40.0, 0.0, 60.0, 80.0], 10),
    }
)
full["level"] = pd.Categorical(np.resize([2, 1, 3], len(full)), categories=[2, 1, 3], ordered=True)
full["flag"] = pd.Categorical(
    np.resize([True, False], len(full)), categories=[True, False], ordered=True
)
development, final = azoic.split_portfolio(full, list(range(60, 80)), id_col="id")
config = azoic.ExperimentConfig(
    data_path="not-read.parquet",
    features=["x", "level", "flag"],
    spec=azoic.DatasetSpec(target="amount", exposure="e", id_col="id", currency="EUR"),
    preprocessing=azoic.PreprocessingSpec(binner={"cols": ["x"], "max_bins": 3}),
    models={"glm": azoic.ModelSpec(params={"family": "tweedie", "link": "log"})},
)
run, estimators = azoic.run_experiment(config, df=development, return_estimators=True)
evaluated = azoic.evaluate_final(
    run,
    estimators,
    model="glm",
    df=final,
    final_test_ids=final.id.tolist(),
    rationale="Installed selection",
)
with tempfile.TemporaryDirectory() as folder:
    directory = Path(folder)
    azoic.save_run(evaluated, estimators, directory / "evaluated.pkl")
    evaluated, estimators = azoic.load_run(directory / "evaluated.pkl")
    production, fitted = azoic.refit_production(
        evaluated, estimators, df=full, rationale="Installed refit"
    )
    assert not production.final_evaluation and production.n_test == 0
    path = azoic.export_production(
        production,
        fitted,
        cases=pd.DataFrame({"x": [1.0, 3.0], "level": [2, 1], "flag": [True, False]}),
        feature_units={"x": "dimensionless", "level": "category", "flag": "category"},
        out=directory / "bundle",
    )
    subprocess.run([sys.executable, str(path.parent / "score.py")], cwd=directory, check=True)
    full[["id", "x", "level", "flag", "e"]].to_parquet(directory / "input.parquet")
    subprocess.run(
        [
            sys.executable,
            str(path.parent / "score.py"),
            str(directory / "input.parquet"),
            str(directory / "rates.csv"),
        ],
        cwd=directory,
        check=True,
    )
    output = pd.read_csv(directory / "rates.csv")
    np.testing.assert_allclose(
        output.predicted_rate, fitted["glm"].predict(full[["x", "level", "flag"]])
    )
    np.testing.assert_allclose(output.predicted_period_cost, output.predicted_rate * full.e)
print("Frozen final evaluation, full refit and fresh-process production agreement/scoring passed")
