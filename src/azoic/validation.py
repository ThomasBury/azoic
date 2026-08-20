"""Validation helpers: stratum labels for stratified splits, temporal split,
single-shot stratified random split.

Three thin function helpers, not splitter classes -- sklearn already has the
splitters (``StratifiedKFold`` / ``StratifiedGroupKFold`` / ``TimeSeriesSplit``).
``make_strata`` discretizes a continuous y so sklearn's stratifiers work on
pure-premium / claim-count targets; ``temporal_split`` is the single-
holdout case (one cutoff, no leakage) that ``TimeSeriesSplit`` does not cover
directly; ``stratified_random_split`` is the ``train_test_split(stratify=...)``
case for low-frequency events where a random shuffle can leave the test set
with an unrepresentative share of positives (claim presence is the canonical
actuarial example).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedShuffleSplit

__all__ = ["make_strata", "temporal_split", "stratified_random_split"]


def _weighted_quantile_edges(y, sample_weight, *, n_quantiles: int) -> np.ndarray:
    """``n_quantiles - 1`` unique weighted-quantile edges of ``y`` (sorted)."""
    y = np.asarray(y, dtype=float)
    w = np.asarray(sample_weight, dtype=float)
    if w.shape != y.shape:
        raise ValueError(f"`sample_weight` shape {w.shape} does not match `y` shape {y.shape}")
    order = np.argsort(y, kind="stable")
    ys, ws = y[order], w[order]
    cum = np.cumsum(ws)
    total = float(cum[-1])
    if total <= 0:
        return np.array([])
    qs = np.linspace(0.0, total, n_quantiles + 1)[1:-1]
    idx = np.clip(np.searchsorted(cum, qs, side="right"), 0, len(ys) - 1)
    return np.unique(ys[idx])


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
    """
    y = np.asarray(y, dtype=float)
    if sample_weight is None:
        codes = pd.qcut(pd.Series(y), n_strata, labels=False, duplicates="drop")
        return codes.fillna(-1).astype(int).to_numpy()
    w = np.asarray(sample_weight, dtype=float)
    edges = _weighted_quantile_edges(y, w, n_quantiles=n_strata)
    if edges.size == 0:
        return np.zeros(len(y), dtype=int)
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


def stratified_random_split(
    strata,
    *,
    test_size: float | int,
    random_state: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Positional ``(train_idx, test_idx)`` from a single stratified random split.

    Thin wrapper around ``sklearn.StratifiedShuffleSplit`` that returns
    positional indices, mirroring ``temporal_split``. Use when a naive random
    shuffle can produce a test partition with an unrepresentative share of the
    rare class -- claim presence (``(claim_count > 0).astype(int)``) is the
    actuarial default for low-frequency events.

    ``test_size`` follows ``train_test_split`` conventions: float in ``(0, 1)``
    is the fraction of rows; int is the absolute count and must satisfy
    ``1 <= n_test < n``.

    Returns
    -------
    (ndarray[int], ndarray[int])
        Positional row indices (use ``df.iloc[...]``). Disjoint, together
        cover the full input length. Strata classes of size < 2 raise --
        sklearn rejects them.

    ponytail: returns positional indices only -- a single holdout does not need
      a sklearn splitter; for K-fold stratified CV use ``StratifiedKFold`` with
      ``make_strata`` codes.
    """
    strata = np.asarray(strata)
    n = len(strata)
    if n == 0:
        raise ValueError("strata is empty")
    _, counts = np.unique(strata, return_counts=True)
    if (counts < 2).any():
        raise ValueError("each stratum must contain at least 2 rows")
    splitter = StratifiedShuffleSplit(
        n_splits=1,
        test_size=test_size,
        random_state=random_state,
    )
    train, test = next(splitter.split(np.zeros(n), strata))
    if len(train) == 0 or len(test) == 0:
        raise ValueError("stratified_random_split produces an empty train or test partition")
    return train, test
