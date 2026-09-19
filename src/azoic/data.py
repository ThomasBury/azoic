"""Dataset specifications and loaders.

pandas / pyarrow at boundaries. S3 paths work out of the box via fsspec when
the optional ``aws`` extra is installed (`uv sync --extra aws`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field, field_validator, model_validator

MIN_EXPOSURE = 1.0 / 366.0
"""Minimum per-row exposure: one day in year fractions (leap-year denominator).

Sub-day rows are data errors for pure-premium modelling: a tiny exposure
inflates ``claim_amount / exposure`` rates and destabilizes GLM fits.
"""
EXPOSURE_FLOOR = MIN_EXPOSURE * (1.0 - 1e-3)
"""Validation threshold: one day minus a 0.1% relative tolerance for day-count
representations (freMTPL2 stores one-day policies ~163 ulps below 1/366)."""


class DatasetSpec(BaseModel):
    """Names of the special (non-feature) columns in a pricing dataset.

    Feature columns are everything else. `.target` and `.exposure` are required;
    the rest are optional and used by downstream modules as they land.
    """

    target: str
    exposure: str
    claim_count: str | None = None
    time_col: str | None = None
    protected_cols: list[str] = Field(default_factory=list)

    @field_validator("target", "exposure", "claim_count", "time_col")
    @classmethod
    def _non_empty(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("column name must be non-empty")
        return v

    @field_validator("protected_cols")
    @classmethod
    def _valid_protected_cols(cls, values: list[str]) -> list[str]:
        if any(not name or not name.strip() for name in values):
            raise ValueError("protected column names must be non-empty")
        duplicates = sorted({name for name in values if values.count(name) > 1})
        if duplicates:
            raise ValueError(f"protected_cols must be unique; duplicates: {duplicates}")
        return values

    @model_validator(mode="after")
    def _protected_cols_are_not_outcomes(self):
        special = {self.target, self.exposure, self.claim_count, self.time_col}
        overlap = sorted(set(self.protected_cols) & special)
        if overlap:
            raise ValueError(f"protected_cols overlaps other special columns: {overlap}")
        return self

    @model_validator(mode="after")
    def _special_cols_are_distinct(self):
        names = [self.target, self.exposure, self.claim_count, self.time_col]
        present = [name for name in names if name is not None]
        duplicates = sorted({name for name in present if present.count(name) > 1})
        if duplicates:
            raise ValueError(f"special column names must be distinct; duplicates: {duplicates}")
        return self

    def required_columns(self) -> list[str]:
        cols = [self.target, self.exposure]
        for opt in (self.claim_count, self.time_col):
            if opt:
                cols.append(opt)
        cols.extend(self.protected_cols)
        return cols


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
