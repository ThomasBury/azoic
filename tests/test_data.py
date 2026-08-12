"""Tests for riskforge.data: DatasetSpec validation and load_data round-trip."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pydantic
import pytest

from riskforge.data import DatasetSpec, load_data
from tests.conftest import make_synthetic_portfolio


def test_dataset_spec_requires_target_and_exposure() -> None:
    spec = DatasetSpec(target="claim_amount", exposure="exposure", claim_count="claim_count")
    assert spec.target == "claim_amount"
    assert spec.claim_count == "claim_count"
    assert "claim_amount" in spec.required_columns()
    assert "exposure" in spec.required_columns()
    assert "claim_count" in spec.required_columns()


def test_dataset_spec_rejects_empty_strings() -> None:
    with pytest.raises(pydantic.ValidationError):
        DatasetSpec(target="", exposure="exposure")
    with pytest.raises(pydantic.ValidationError):
        DatasetSpec(target="claim_amount", exposure="   ")


def test_dataset_spec_optional_columns_filter() -> None:
    spec = DatasetSpec(target="claim_amount", exposure="exposure")
    assert spec.required_columns() == ["claim_amount", "exposure"]


def test_load_data_roundtrip(tmp_path) -> None:
    df = make_synthetic_portfolio(n=500, seed=3)
    p = tmp_path / "port.parquet"
    df.to_parquet(p)
    spec = DatasetSpec(target="claim_amount", exposure="exposure", claim_count="claim_count")
    df2 = load_data(p, spec=spec)
    pd.testing.assert_frame_equal(df, df2)


def test_load_data_missing_columns_raises(tmp_path) -> None:
    df = pd.DataFrame(
        {
            "exposure": np.linspace(0.5, 1.0, 10),
            "driver_age": np.repeat(30, 10),
        }
    )
    p = tmp_path / "bad.parquet"
    df.to_parquet(p)
    spec = DatasetSpec(target="claim_amount", exposure="exposure")
    with pytest.raises(ValueError, match="missing required columns"):
        load_data(p, spec=spec)


def test_load_data_without_spec(tmp_path) -> None:
    df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    p = tmp_path / "plain.parquet"
    df.to_parquet(p)
    pd.testing.assert_frame_equal(load_data(p), df)
