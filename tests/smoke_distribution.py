"""Runtime-only check: copy outside the checkout and run against each installed artifact."""

from importlib import import_module
from importlib.metadata import distribution
from pathlib import Path

import numpy as np
import pandas as pd

import azoic
from azoic.models import RiskGBM, RiskGLM

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
