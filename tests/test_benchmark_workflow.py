"""The opt-in measurement must catch refitting and changed consumer outputs."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.benchmark_workflow import Meter


@pytest.mark.skipif(sys.platform != "linux", reason="benchmark samples Linux process RSS")
def test_benchmark_fresh_process_roundtrip(tmp_path):
    out = tmp_path / "measurement"
    command = [
        sys.executable,
        str(Path(__file__).with_name("benchmark_workflow.py")),
        "--rows",
        "500",
        "--out",
        str(out),
    ]
    subprocess.run(command, check=True)
    fitted, saved, environment = [
        json.loads((out / f"{name}.json").read_text()) for name in ("fit", "resume", "environment")
    ]
    assert environment["consumer_outputs_equal"]
    assert environment["avoided_fit_calls"] == {"preprocessing_fit": 2, "model_fit": 2}
    assert environment["avoided_fit_seconds"] > 0
    assert fitted["data_fingerprint"] == saved["data_fingerprint"]
    assert fitted["n_train"] + fitted["n_validation"] == 500
    assert "preprocessing_fit" not in saved["stages"]
    assert "model_fit" not in saved["stages"]
    for result in (fitted, saved):
        assert result["arrow_cpu_threads"] == result["arrow_io_threads"] == 1
        assert all(pool["num_threads"] == 1 for pool in result["threadpools"])
        assert result["unattributed_seconds"] >= 0
        assert result["process_peak_rss_mib"] > 0
        for row in result["stages"].values():
            assert row["calls"] > 0 and row["seconds"] > 0 and row["sampled_peak_rss_mib"] > 0
    repeated = subprocess.run(command, capture_output=True, text=True)
    assert repeated.returncode != 0
    assert "FileExistsError" in repeated.stderr
    assert json.loads((out / "environment.json").read_text()) == environment


@pytest.mark.skipif(sys.platform != "linux", reason="benchmark samples Linux process RSS")
def test_meter_attributes_separate_stages_and_recovers_after_failure():
    meter = Meter()

    def reject():
        raise ValueError("deliberate failure")

    with meter.running():
        assert meter.wrap("loading", lambda: 42)() == 42
        with pytest.raises(ValueError, match="deliberate failure"):
            meter.wrap("fitting", reject)()
        assert meter.active is None
        assert meter.wrap("loading", lambda: 43)() == 43
    assert meter.stages["loading"]["calls"] == 2
    assert meter.stages["fitting"]["calls"] == 1
    assert all(stage["sampled_peak_rss_mib"] > 0 for stage in meter.stages.values())
