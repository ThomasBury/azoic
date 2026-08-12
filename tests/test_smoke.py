"""Smoke test: package imports and the core dependency stack is importable."""

from riskforge import __version__


def test_version() -> None:
    assert __version__ == "0.1.0"


def test_core_dependencies_importable() -> None:
    import glum  # noqa: F401
    import lightgbm  # noqa: F401
    import numpy
    import pandas
    import pyarrow  # noqa: F401
    import sklearn

    assert numpy.__version__
    assert pandas.__version__
    assert sklearn.__version__
