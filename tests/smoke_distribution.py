"""Runtime-only check: copy outside the checkout and run against each installed artifact."""

import subprocess
import warnings
from importlib import import_module
from importlib.metadata import distribution
from pathlib import Path
from unittest import TestCase

import numpy as np
import pandas as pd

import azoic
from azoic.models import RiskGBM, RiskGLM
from azoic.preprocessing import AutoBinner, AutoGrouper

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
for command in ("profile", "fit", "compare", "export-tariff", "tune"):
    result = subprocess.run(
        ["azoic", command, "--help"], check=True, capture_output=True, text=True
    )
    assert "Usage:" in result.stdout, command
print("Preprocessing outcome/column contracts, constant bins, and all five CLI helps passed")
