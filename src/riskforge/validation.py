"""Validation helpers: stratum labels for stratified splits, temporal split.

Two thin function helpers, not splitter classes -- sklearn already has the
splitters (``StratifiedKFold`` / ``StratifiedGroupKFold`` / ``TimeSeriesSplit``).
``make_strata`` discretizes a continuous y so sklearn's stratifiers work on
pure-premium / claim-count targets; ``temporal_split`` is the single-
holdout case (one cutoff, no leakage) that ``TimeSeriesSplit`` does not cover
directly.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["make_strata", "temporal_split"]


def make_strata(y, sample_weight=None, *, n_strata: int = 10) -> np.ndarray:
    """Integer stratum labels for a continuous y, for sklearn's stratifiers.

    sklearn's ``StratifiedKFold`` / ``StratifiedGroupKFold`` stratify on
    discrete classes; pure-premium / claim-count targets are continuous.
    Discretize into ``n_strata`` quantiles of ``y`` -- exposure-weighted when
    ``sample_weight`` is given (each fold then carries similar portfolio
    adequacy, the actuarial CV convention) -- and feed the codes back to the
    splitter as the stratification target.

    Returns
    -------
    ndarray[int]
        Integer codes (``-1`` for NaN rows); distinct positive codes count
        ``<= n_strata`` when ``y`` has fewer unique values. The unweighted
        path inherits pandas ``qcut`` behaviour of skipping the indices of
        dropped duplicate edges, so the label set need not be ``0..k-1``
        contiguous -- sklearn stratifiers only need distinct labels. Drop
        ``-1`` rows or remap to ``0`` before passing to a splitter that
        rejects negative labels.

    ponytail: integer labels only; the splitter does the actual folding. The
      weighted path uses cumulative-exposure searchsorted edges, same pattern
      as ``AutoBinner._quantile_edges`` -- duplicated rather than coupled, M6
      may factor a shared helper if a third copy shows up.
    """
    y = np.asarray(y, dtype=float)
    if sample_weight is None:
        codes = pd.qcut(pd.Series(y), n_strata, labels=False, duplicates="drop")
        return codes.fillna(-1).astype(int).to_numpy()
    w = np.asarray(sample_weight, dtype=float)
    if w.shape != y.shape:
        raise ValueError(f"`sample_weight` shape {w.shape} does not match `y` shape {y.shape}")
    order = np.argsort(y, kind="stable")
    ys, ws = y[order], w[order]
    cum = np.cumsum(ws)
    total = float(cum[-1])
    if total <= 0:
        return np.zeros(len(y), dtype=int)
    qs = np.linspace(0.0, total, n_strata + 1)[1:-1]
    idx = np.clip(np.searchsorted(cum, qs, side="right"), 0, len(ys) - 1)
    edges = np.unique(ys[idx])
    codes = np.searchsorted(edges, y, side="right")
    return np.where(np.isnan(y), -1, codes).astype(int)


def temporal_split(
    df: pd.DataFrame,
    time_col: str,
    *,
    test_size: int | float | None = None,
    cutoff=None,
) -> tuple[np.ndarray, np.ndarray]:
    """Return positional ``(train_idx, test_idx)`` for a single temporal holdout.

    Rows are sorted by ``time_col`` (ascending) regardless of input order, so
    the train block precedes the test block in time -- no leakage. Pass exactly
    one of:

    ``test_size``
        Fraction in ``(0, 1)`` or an int selects the latest rows for test. If the
        boundary falls inside a timestamp tie, the whole tied block goes to test.
    ``cutoff``
        Timestamp / scalar comparable to ``df[time_col]``. Rows with
        ``time <= cutoff`` go to train; ``time > cutoff`` go to test.

    Returns
    -------
    (ndarray[int], ndarray[int])
        Positional row indices into the *input* ``df`` (use ``df.iloc[...]``).

    ponytail: returns positional indices only -- a single holdout does not need
      a sklearn splitter; for walk-forward OOT use ``TimeSeriesSplit``.
    """
    if (test_size is None) == (cutoff is None):
        raise ValueError("pass exactly one of `test_size` or `cutoff`")
    if time_col not in df.columns:
        raise ValueError(f"`time_col` {time_col!r} not in df.columns")
    values = df[time_col].to_numpy()
    if pd.isna(values).any():
        raise ValueError(f"`time_col` {time_col!r} contains missing values")
    order = np.argsort(values, kind="stable")
    times = values[order]

    if cutoff is not None:
        cut_pos = int(np.searchsorted(times, cutoff, side="right"))
    else:
        if test_size is None:
            raise ValueError("pass exactly one of `test_size` or `cutoff`")
        n = len(df)
        if isinstance(test_size, float):
            if not 0.0 < test_size < 1.0:
                raise ValueError(f"`test_size` float must be in (0, 1), got {test_size}")
            n_test = int(round(n * test_size))
        else:
            n_test = int(test_size)
        if not 0 < n_test < n:
            raise ValueError(f"`test_size` resolves to {n_test} rows; must be 1..{n - 1}")
        boundary = times[n - n_test]
        cut_pos = int(np.searchsorted(times, boundary, side="left"))

    train, test = order[:cut_pos], order[cut_pos:]
    if len(train) == 0 or len(test) == 0:
        raise ValueError("temporal split produces an empty train or test partition")
    return train, test
