"""Public package exports stay discoverable without importing backends."""

import subprocess
import sys
from importlib import import_module


def test_package_exports_are_lazy_and_discoverable():
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
import azoic
backends = {"pandas", "numpy", "glum", "lightgbm", "matplotlib", "optuna", "mlflow"}
assert not backends & sys.modules.keys()
assert set(azoic.__all__) <= set(dir(azoic))
assert "RiskGLM" in dir(azoic) and "run_experiment" in dir(azoic)
from azoic.models import RiskGLM
assert azoic.RiskGLM is RiskGLM
assert azoic.RiskGLM is azoic.RiskGLM
try:
    azoic.not_an_export
except AttributeError:
    pass
else:
    raise AssertionError("unknown exports must raise AttributeError")
""",
        ],
        check=True,
    )


def test_package_reexports_module_public_apis():
    import azoic

    for module_name in set(azoic._EXPORTS.values()):
        module = import_module(f"azoic.{module_name}")
        names = getattr(
            module, "__all__", ["DatasetSpec", "load_data", "MIN_EXPOSURE", "EXPOSURE_FLOOR"]
        )
        for name in names:
            assert name in azoic.__all__
            assert getattr(azoic, name) is getattr(module, name)
