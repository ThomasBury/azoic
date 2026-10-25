"""Dataset specifications and loaders.

pandas / pyarrow at boundaries. S3 paths work out of the box via fsspec when
the optional ``aws`` extra is installed (`uv sync --extra aws`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator
from sklearn.utils.validation import check_consistent_length

MIN_EXPOSURE = 1.0 / 366.0
"""Minimum per-row exposure: one day in year fractions (leap-year denominator).

Sub-day rows are data errors for pure-premium modelling: a tiny exposure
inflates ``claim_amount / exposure`` rates and destabilizes GLM fits.
"""
EXPOSURE_FLOOR = MIN_EXPOSURE * (1.0 - 1e-3)
"""Validation threshold: one day minus a 0.1% relative tolerance for day-count
representations (freMTPL2 stores one-day policies ~163 ulps below 1/366)."""

__all__ = ["DatasetSpec", "load_data", "split_portfolio", "MIN_EXPOSURE", "EXPOSURE_FLOOR"]


def _raise_for_rows(message: str, invalid: np.ndarray) -> None:
    if invalid.any():
        positions = np.flatnonzero(invalid)
        raise ValueError(
            f"{message}; {len(positions)} invalid rows; "
            f"row positions (0-based, first 5): {positions[:5].tolist()}"
        ) from None


def _validate_outcomes(exposure, claim_amount, claim_count=None) -> None:
    """Validate portfolio rows, independently of schema and model-weight policies."""
    outcomes = [("exposure", exposure), ("claim_amount", claim_amount)]
    if claim_count is not None:
        outcomes.append(("claim_count", claim_count))
    arrays, names = [], []
    for role, values in outcomes:
        name = f"{role} (column {getattr(values, 'name', role)!r})"
        if np.ndim(values) != 1:
            raise ValueError(f"portfolio outcomes must be one-dimensional: {name}")
        try:
            array = np.asarray(values, dtype=float)
        except (TypeError, ValueError):
            invalid = pd.to_numeric(pd.Series(values), errors="coerce").isna().to_numpy()
            _raise_for_rows(f"{name} must contain only numeric finite values", invalid)
            raise
        arrays.append(array)
        names.append(name)
    check_consistent_length(*arrays)
    exposure, claim_amount = arrays[:2]
    _raise_for_rows(
        f"{names[0]} must contain only positive finite values",
        ~np.isfinite(exposure) | (exposure <= 0),
    )
    _raise_for_rows(
        f"{names[0]} must be at least 1/366 (one day of exposure)", exposure < EXPOSURE_FLOOR
    )
    _raise_for_rows(
        f"{names[1]} must contain only non-negative finite values",
        ~np.isfinite(claim_amount) | (claim_amount < 0),
    )
    if claim_count is not None:
        claim_count = arrays[2]
        _raise_for_rows(
            f"{names[2]} must contain only non-negative finite values",
            ~np.isfinite(claim_count) | (claim_count < 0),
        )
        _raise_for_rows(
            f"{names[2]} and {names[1]} rows must be zero or positive together",
            (claim_count == 0) != (claim_amount == 0),
        )


class DatasetSpec(BaseModel):
    """Names of the special (non-feature) columns in a pricing dataset.

    Feature columns exclude every declared column role, including ``id_col``
    and ``excluded_cols`` (incumbent rates and partition metadata, for example).
    Exposure is always in years. Currency, observation period, claim valuation
    basis and upstream adjustments are descriptive evidence, not transformations.
    Unknown fields are rejected.
    """

    model_config = ConfigDict(extra="forbid")

    target: str
    exposure: str
    claim_count: str | None = None
    time_col: str | None = None
    protected_cols: list[str] = Field(default_factory=list)
    id_col: str | None = None
    excluded_cols: list[str] = Field(default_factory=list)
    exposure_unit: Literal["year"] = "year"
    currency: str | None = None
    observation_period: str | None = None
    claim_valuation_basis: str | None = None
    adjustments: list[str] = Field(default_factory=list)

    @field_validator(
        "target",
        "exposure",
        "claim_count",
        "time_col",
        "id_col",
        "currency",
        "observation_period",
        "claim_valuation_basis",
    )
    @classmethod
    def _non_empty(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("name or portfolio description must be non-empty")
        return v

    @field_validator("protected_cols", "excluded_cols", "adjustments")
    @classmethod
    def _valid_entries(cls, values: list[str], info: ValidationInfo) -> list[str]:
        if any(not name or not name.strip() for name in values):
            raise ValueError(f"{info.field_name} entries must be non-empty")
        duplicates = sorted({name for name in values if values.count(name) > 1})
        if duplicates:
            raise ValueError(f"{info.field_name} must be unique; duplicates: {duplicates}")
        return values

    @model_validator(mode="after")
    def _protected_cols_are_not_outcomes(self):
        special = {self.target, self.exposure, self.claim_count, self.time_col, self.id_col}
        overlap = sorted(set(self.protected_cols) & special)
        if overlap:
            raise ValueError(f"protected_cols overlaps other special columns: {overlap}")
        overlap = sorted(set(self.excluded_cols) & (special | set(self.protected_cols)))
        if overlap:
            raise ValueError(f"excluded_cols overlaps other special columns: {overlap}")
        return self

    @model_validator(mode="after")
    def _special_cols_are_distinct(self):
        names = [self.target, self.exposure, self.claim_count, self.time_col, self.id_col]
        present = [name for name in names if name is not None]
        duplicates = sorted({name for name in present if present.count(name) > 1})
        if duplicates:
            raise ValueError(f"special column names must be distinct; duplicates: {duplicates}")
        return self

    def required_columns(self) -> list[str]:
        cols = [self.target, self.exposure]
        for opt in (self.claim_count, self.time_col, self.id_col):
            if opt:
                cols.append(opt)
        cols.extend(self.protected_cols)
        cols.extend(self.excluded_cols)
        return cols


def _validate_record_ids(ids: pd.Series) -> None:
    _raise_for_rows(f"record ID column {ids.name!r} must not be missing", ids.isna().to_numpy())
    _raise_for_rows(
        f"record ID column {ids.name!r} must be unique", ids.duplicated(keep=False).to_numpy()
    )
    _raise_for_rows(
        f"record ID column {ids.name!r} must contain strings or integers",
        ~ids.map(lambda value: isinstance(value, (str, int, np.integer))).to_numpy(dtype=bool),
    )


def split_portfolio(
    df: pd.DataFrame, final_test_ids: list[str | int] | tuple[str | int, ...], *, id_col: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separate development and final-test copies by predeclared unique record IDs.

    Returns ``(development, final_test)`` in source row order, preserving index
    labels. Save both portfolios and their ID lists before inspecting outcomes.
    Membership uses IDs only; no outcome validation, repair, caps or fitting is
    performed here. Unused categorical levels are removed within each partition.
    IDs must be nonmissing unique strings or integers. Both partitions must be
    nonempty and every requested final-test ID must exist.
    """
    if not df.columns.is_unique:
        raise ValueError("dataset column names must be unique")
    if id_col not in df.columns:
        raise ValueError(f"dataset is missing record ID column {id_col!r}")
    ids = df[id_col]
    _validate_record_ids(ids)
    requested = pd.Series(final_test_ids, name=id_col)
    _validate_record_ids(requested)
    _raise_for_rows(
        f"final-test IDs must exist in column {id_col!r}", ~requested.isin(ids).to_numpy()
    )
    mask = ids.isin(requested)
    if not mask.any() or mask.all():
        raise ValueError("development and final-test portfolios must both be nonempty")
    development, final_test = df.loc[~mask].copy(deep=True), df.loc[mask].copy(deep=True)
    for frame in (development, final_test):
        for column in frame.select_dtypes(include="category"):
            frame[column] = frame[column].cat.remove_unused_categories()
    return development, final_test


def load_data(path: str | Path, spec: DatasetSpec | None = None, **kwargs: Any) -> pd.DataFrame:
    """Read a Parquet dataset (local or s3://) into a pandas DataFrame.

    When ``spec`` is given, required columns must be present or ValueError.
    Extra kwargs forward to ``pandas.read_parquet``.
    """
    df = pd.read_parquet(path, **kwargs)
    if spec is not None:
        missing = [c for c in spec.required_columns() if c not in df.columns]
        if missing:
            raise ValueError(f"loaded dataset is missing required columns: {missing}")
    return df
