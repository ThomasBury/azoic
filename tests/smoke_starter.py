"""Run the exact starter docs with runtime dependencies, outside the checkout.

Usage: python smoke_starter.py /path/to/copied/docs
"""

import os
import subprocess
import sys
from importlib.metadata import distribution
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

import azoic

docs = Path(sys.argv[1]).resolve()
starter = (docs / "getting-started/first-model.md").read_text(encoding="utf-8")
guide = (docs / "guide/experiment-configuration.md").read_text(encoding="utf-8")
recipe = starter.split("```python\n", 1)[1].split("```", 1)[0]
config_yaml = guide.split("```yaml\n", 1)[1].split("```", 1)[0]
config_python = guide.split("```python\n", 1)[1].split("```", 1)[0]
installed = distribution("azoic")
assert Path(azoic.__file__).resolve() == Path(installed.locate_file("azoic/__init__.py")).resolve()
print(f"Installed Azoic {installed.version}: {azoic.__file__}")

original_directory = Path.cwd()
with TemporaryDirectory() as directory:
    try:
        os.chdir(directory)
        namespace = {}
        exec(compile(recipe, "first_model.py", "exec"), namespace)
        portfolio = namespace["portfolio"]
        validation = namespace["validation"]
        assert namespace["features"] == ["driver_age", "vehicle_age", "region"]
        assert len(portfolio) == 5_000
        assert namespace["train"]["period"].max() < validation["period"].min()
        assert np.isfinite(namespace["diagnostics"].to_numpy()).all()
        pd.testing.assert_frame_equal(pd.read_parquet("portfolio.parquet"), portfolio)
        for name, prediction in namespace["predictions"].items():
            assert prediction.shape == (len(validation),)
            assert np.isfinite(prediction).all() and (prediction > 0).all()
            assert Path(f"first-model-{name}-calibration.png").stat().st_size > 0

        # Independent arithmetic from the workbook, with no model/preprocessing calls.
        sheets = pd.read_excel("first-model-tariff.xlsx", sheet_name=None)
        assert list(sheets) == ["base_rate", "factors", "mappings"]
        assert not sheets["base_rate"].iloc[0]["recalibrated"]
        rate = np.full(len(validation), sheets["base_rate"].iloc[0]["base_rate"])
        for feature, factors in sheets["factors"].groupby("feature"):
            (application,) = factors["application"].unique()
            if application == "raise_factor ** value":
                assert len(factors) == 1
                rate *= factors.iloc[0]["multiplicative_factor"] ** validation[feature].to_numpy()
            else:
                assert application == "multiply_by_factor_matching_level"
                levels = factors.set_index("level")["multiplicative_factor"]
                rate *= validation[feature].map(levels).to_numpy(dtype=float)
        np.testing.assert_allclose(rate, namespace["predictions"]["glm"], rtol=1e-10)

        Path("experiment.yaml").write_text(config_yaml, encoding="utf-8")
        exec(compile(config_python, "configuration.py", "exec"), namespace)
        for name, estimator in namespace["estimators"].items():
            np.testing.assert_allclose(
                estimator.predict(validation[namespace["model_columns"]]),
                namespace["predictions"][name.removeprefix("tweedie-")],
                rtol=1e-10,
            )
        subprocess.run(
            [
                sys.executable,
                "-m",
                "azoic.cli",
                "fit",
                "--config",
                "experiment.yaml",
                "--out",
                "model-card.md",
                "--quiet",
            ],
            check=True,
        )
        assert Path("model-card.md").stat().st_size > 0
        print("Starter, workbook rates, Python/YAML predictions and CLI fit passed")
    finally:
        os.chdir(original_directory)
