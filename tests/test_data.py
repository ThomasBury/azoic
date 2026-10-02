"""Tests for azoic.data: DatasetSpec validation and load_data round-trip."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pydantic
import pytest

from azoic.data import DatasetSpec, load_data
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
    assert spec.protected_cols == []
    assert spec.required_columns() == ["claim_amount", "exposure"]


def test_dataset_spec_rejects_misspelled_optional_column() -> None:
    with pytest.raises(pydantic.ValidationError, match="claim_count_col"):
        DatasetSpec.model_validate(
            {"target": "claim_amount", "exposure": "exposure", "claim_count_col": "claim_count"}
        )


@pytest.mark.parametrize(
    ("protected_cols", "message"),
    [
        (["region", "region"], "unique"),
        ([""], "non-empty"),
        (["   "], "non-empty"),
    ],
)
def test_dataset_spec_rejects_invalid_protected_names(
    protected_cols: list[str], message: str
) -> None:
    with pytest.raises(pydantic.ValidationError, match=message):
        DatasetSpec(
            target="claim_amount",
            exposure="exposure",
            protected_cols=protected_cols,
        )


@pytest.mark.parametrize("column", ["claim_amount", "exposure", "claim_count", "period"])
def test_dataset_spec_rejects_protected_special_column_overlap(column: str) -> None:
    with pytest.raises(pydantic.ValidationError, match="overlaps"):
        DatasetSpec(
            target="claim_amount",
            exposure="exposure",
            claim_count="claim_count",
            time_col="period",
            protected_cols=[column],
        )


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


def test_load_data_requires_declared_protected_columns(tmp_path) -> None:
    path = tmp_path / "missing-protected.parquet"
    pd.DataFrame({"claim_amount": [0.0], "exposure": [1.0]}).to_parquet(path)
    spec = DatasetSpec(
        target="claim_amount",
        exposure="exposure",
        protected_cols=["review_group"],
    )

    with pytest.raises(ValueError, match="review_group"):
        load_data(path, spec=spec)


def test_load_data_without_spec(tmp_path) -> None:
    df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    p = tmp_path / "plain.parquet"
    df.to_parquet(p)
    pd.testing.assert_frame_equal(load_data(p), df)


# ---------------------------------------------------------------------------
# Special-column distinctness (M32)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"target": "amount", "exposure": "amount"},
        {"target": "amount", "exposure": "e", "claim_count": "amount"},
        {"target": "t", "exposure": "e", "claim_count": "c", "time_col": "c"},
        {"target": "t", "exposure": "e", "claim_count": "e", "time_col": "t"},
    ],
)
def test_dataset_spec_rejects_aliased_special_columns(overrides) -> None:
    """Aliased specials previously produced a constant response (amount/amount == 1)."""
    with pytest.raises(pydantic.ValidationError, match="must be distinct"):
        DatasetSpec(**overrides)


def test_dataset_spec_accepts_distinct_optional_columns() -> None:
    spec = DatasetSpec(target="t", exposure="e", claim_count="c", time_col="p")
    assert spec.required_columns() == ["t", "e", "c", "p"]


@pytest.mark.parametrize("field", ["target", "exposure", "claim_count", "time_col"])
def test_dataset_spec_rejects_empty_special_names(field) -> None:
    """Empty optional names previously passed validation and failed later
    with a bare KeyError."""
    base = {"target": "t", "exposure": "e"}
    base[field] = ""
    with pytest.raises(pydantic.ValidationError, match="non-empty"):
        DatasetSpec(**base)
