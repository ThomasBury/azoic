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


def test_reporting_annotations_resolve_without_eager_workflow_imports():
    for module_name, functions in (
        ("reporting", ["model_card", "comparison_table", "comparison_dashboard"]),
        ("mlops", ["log_run"]),
    ):
        subprocess.run(
            [
                sys.executable,
                "-c",
                f"""
import sys
import typing
import azoic
from azoic import {module_name} as module
assert not {{"azoic.workflow", "glum", "lightgbm"}} & sys.modules.keys()
for name in {functions!r}:
    hints = typing.get_type_hints(getattr(module, name))
    annotation = hints.get("run")
    if annotation is not None:
        assert annotation is azoic.Run
    else:
        assert typing.get_args(hints["runs"]) == (azoic.Run,)
from azoic.workflow import Run, ModelResult
assert azoic.Run is Run and azoic.ModelResult is ModelResult
assert Run.model_fields["config"].annotation is azoic.ExperimentConfig
""",
            ],
            check=True,
        )


def test_downstream_public_typing(tmp_path):
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    fixture = root / "tests/typing_public_api.py"
    result = subprocess.run(
        [sys.executable, "-m", "ty", "check", str(fixture)],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    invalid = tmp_path / "invalid_consumer.py"
    invalid.write_text(
        "from azoic import ExperimentConfig, Run, run_experiment\n"
        "def invalid(config: ExperimentConfig):\n"
        "    result: Run = run_experiment(config, return_estimators=True)\n"
        "    return result\n"
    )
    result = subprocess.run(
        [sys.executable, "-m", "ty", "check", str(invalid)],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "invalid-assignment" in result.stdout, result.stdout + result.stderr
