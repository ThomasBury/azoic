"""Feature profiling and screening (actuary-in-the-loop, before modelling).

``profile_features`` returns one row per column with the cheap stats needed
for screening (missingness, cardinality, zero-variance, dtype, basic numerics).
Per-level actuarial stats live on the binning/grouping transformers' mapping_,
not here -- profiling is for the column-level keep/drop/review decision.

``screen_features`` turns a profile into per-column actions:
``keep`` / ``bin`` (numeric high cardinality) / ``group`` (categorical high
cardinality) / ``drop`` (zero variance or excessive missingness).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["profile_features", "screen_features"]


def profile_features(df: pd.DataFrame) -> pd.DataFrame:
    """One row per column with screening-relevant stats."""
    n = len(df)
    rows = []
    for col in df.columns:
        s = df[col]
        n_missing = int(s.isna().sum())
        n_unique = int(s.nunique(dropna=True))
        is_num = pd.api.types.is_numeric_dtype(s)
        row = {
            "column": col,
            "dtype": str(s.dtype),
            "n": n,
            "n_missing": n_missing,
            "missing_rate": (n_missing / n) if n else np.nan,
            "n_unique": n_unique,
            "numeric": is_num,
            "zero_variance": n_unique <= 1,
        }
        if is_num and n_unique > 0:
            desc = s.describe()
            row.update(
                {
                    "min": float(desc["min"]),
                    "max": float(desc["max"]),
                    "mean": float(desc["mean"]),
                    "std": float(desc["std"]),
                    "n_zeros": int((s == 0).sum()),
                }
            )
        rows.append(row)
    return pd.DataFrame(rows)


def screen_features(
    profile: pd.DataFrame,
    *,
    max_groups: int = 10,
    max_numeric_unique: int = 20,
    missing_drop: float = 0.5,
) -> pd.DataFrame:
    """Per-column recommended action with a one-line reason.

    Rules
    -----
    zero_variance                 -> drop
    missing_rate > missing_drop   -> drop
    numeric & n_unique > max_numeric_unique -> bin
    categorical & n_unique > max_groups      -> group
    else                         -> keep
    """

    def act(row):
        if row["zero_variance"]:
            return ("drop", "zero variance")
        if row["missing_rate"] > missing_drop:
            return ("drop", f"high missingness {row['missing_rate']:.2f}")
        if row["numeric"] and row["n_unique"] > max_numeric_unique:
            return ("bin", f"numeric high cardinality ({row['n_unique']})")
        if not row["numeric"] and row["n_unique"] > max_groups:
            return ("group", f"categorical high cardinality ({row['n_unique']})")
        return ("keep", "")

    res = profile.apply(act, axis=1, result_type="expand")
    res.columns = ["action", "reason"]
    return pd.concat([profile[["column"]], res], axis=1)
