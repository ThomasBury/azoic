"""Dataset specifications and loaders.

pandas / pyarrow at boundaries. S3 paths work out of the box via fsspec when
the optional ``aws`` extra is installed (`uv sync --extra aws`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, field_validator


class DatasetSpec(BaseModel):
    """Names of the special (non-feature) columns in a pricing dataset.

    Feature columns are everything else. `.target` and `.exposure` are required;
    the rest are optional and used by downstream modules as they land.
    """

    target: str
    exposure: str
    claim_count: str | None = None
    time_col: str | None = None

    @field_validator("target", "exposure")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("column name must be non-empty")
        return v

    def required_columns(self) -> list[str]:
        cols = [self.target, self.exposure]
        for opt in (self.claim_count, self.time_col):
            if opt:
                cols.append(opt)
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
