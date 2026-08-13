"""Tests for riskforge.profile: profile_features and screen_features."""

from __future__ import annotations

import numpy as np
import pandas as pd

from riskforge.profile import profile_features, screen_features
from tests.conftest import make_synthetic_portfolio


def test_profile_features_one_row_per_column() -> None:
    df = make_synthetic_portfolio(n=1000, seed=5)
    prof = profile_features(df)
    assert list(prof["column"]) == list(df.columns)
    for needed in (
        "dtype",
        "n",
        "n_missing",
        "missing_rate",
        "n_unique",
        "numeric",
        "zero_variance",
    ):
        assert needed in prof.columns
    assert prof["n"].iloc[0] == len(df)


def test_profile_numeric_columns_get_numerics() -> None:
    df = make_synthetic_portfolio(n=500, seed=6)
    prof = profile_features(df).set_index("column")
    assert np.isfinite(prof.loc["driver_age", "min"])
    assert "mean" in prof.columns and "std" in prof.columns
    assert pd.notna(prof.loc["driver_age", "mean"])


def test_profile_detects_zero_variance_and_missingness() -> None:
    df = pd.DataFrame(
        {
            "constant": [7.0] * 100,
            "with_missing": [np.nan] * 60 + [1.0] * 40,
            "normal": np.linspace(0, 1, 100),
        }
    )
    prof = profile_features(df).set_index("column")
    assert prof.loc["constant", "zero_variance"] is np.True_ or bool(
        prof.loc["constant", "zero_variance"]
    )
    assert prof.loc["with_missing", "missing_rate"] == 0.6


def test_screen_features_actions() -> None:
    df = pd.DataFrame(
        {
            "const": [1.0] * 200,
            "missing": [np.nan] * 150 + [1.0] * 50,
            "hi_card_num": np.arange(200, dtype=float),
            "low_num": np.repeat([1.0, 2.0, 3.0], [67, 67, 66]),
            "low_cat": np.tile(["a", "b"], 100),
            "hi_cat": [f"lvl{i % 50}" for i in range(200)],
        }
    )
    prof = profile_features(df)
    screen = screen_features(
        prof, max_groups=10, max_numeric_unique=20, missing_drop=0.5
    ).set_index("column")
    assert screen.loc["const", "action"] == "drop"
    assert screen.loc["missing", "action"] == "drop"
    assert screen.loc["hi_card_num", "action"] == "bin"
    assert screen.loc["low_num", "action"] == "keep"
    assert screen.loc["low_cat", "action"] == "keep"
    assert screen.loc["hi_cat", "action"] == "group"
    assert "reason" in screen.columns


def test_screen_features_with_synthetic_portfolio() -> None:
    df = make_synthetic_portfolio(n=2000, seed=1)
    prof = profile_features(df)
    screen = screen_features(prof)
    # driver_age + vehicle_age are numeric & high-cardinality -> bin
    assert screen.set_index("column").loc["driver_age", "action"] == "bin"
    assert screen.set_index("column").loc["region", "action"] == "keep"
