"""Tests for azoic.validation: make_strata, temporal_split."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import StratifiedKFold

from azoic.validation import make_strata, temporal_split
from tests.conftest import make_synthetic_portfolio


def test_make_strata_unweighted_returns_expected_label_count() -> None:
    rng = np.random.default_rng(0)
    y = rng.normal(size=2000)
    codes = make_strata(y, n_strata=10)
    assert codes.shape == y.shape
    assert codes.dtype.kind == "i"
    n_unique = np.unique(codes).size
    assert 1 <= n_unique <= 10
    assert n_unique == 10  # continuous y -> all 10 strata appear


def test_make_strata_weighted_balances_exposure_across_strata() -> None:
    rng = np.random.default_rng(21)
    n = 5000
    y = rng.uniform(0.0, 1.0, size=n)  # continuous -> no degenerate zero mass
    w = rng.uniform(0.5, 1.0, size=n)
    codes = make_strata(y, sample_weight=w, n_strata=10)
    per = pd.Series(w).groupby(codes).sum()
    total = float(w.sum())
    lo, hi = 0.75 * total / 10, 1.25 * total / 10
    assert (per >= lo).all() and (per <= hi).all()
    assert per.index.tolist() == list(range(10))


def test_make_strata_unweighted_is_pandas_qcut_label_equivalent() -> None:
    rng = np.random.default_rng(1)
    y = rng.uniform(size=500)
    got = make_strata(y, n_strata=5)
    expected = pd.qcut(pd.Series(y), 5, labels=False, duplicates="drop").astype(int).to_numpy()
    assert np.array_equal(got, expected)


def test_make_strata_low_cardinality_collapses_bins() -> None:
    y = np.array([0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3], dtype=float)
    codes = make_strata(y, n_strata=10)
    # 4 unique y values -> qcut drops duplicate edges and yields fewer than 10
    # labels (pandas keeps the index of surviving edges, so the label set need
    # not be contiguous -- sklearn stratifiers only need distinct labels).
    labels = sorted(np.unique(codes).tolist())
    assert 2 <= len(labels) < 10
    assert all(0 <= c < 10 for c in labels)


def test_make_strata_zero_total_weight_returns_zeros() -> None:
    y = np.linspace(0, 1, 100)
    w = np.zeros(100)
    assert np.array_equal(make_strata(y, sample_weight=w, n_strata=10), np.zeros(100, int))


def test_make_strata_mismatched_weight_shape_raises() -> None:
    with pytest.raises(ValueError, match="shape"):
        make_strata(np.zeros(10), sample_weight=np.zeros(5), n_strata=4)


def test_make_strata_nan_rows_get_minus_one_and_others_have_a_label() -> None:
    y = np.array([0.1, np.nan, 0.9, 0.0, 1.0, np.nan], dtype=float)
    codes = make_strata(y, n_strata=4)
    nan_mask = np.isnan(y)
    assert (codes[nan_mask] == -1).all()
    non_nan_codes = codes[~nan_mask]
    # Non-NaN rows occupy a contiguous range of integer labels starting at 0.
    labels = sorted(set(non_nan_codes.tolist()))
    assert labels == list(range(len(labels)))
    assert len(labels) <= 4


def test_make_strata_works_with_sklearn_stratifiedkfold() -> None:
    df = make_synthetic_portfolio(n=2000, seed=22)
    y = df["claim_count"].to_numpy()
    codes = make_strata(y, df["exposure"].to_numpy(), n_strata=10)
    skf = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
    splits = list(skf.split(np.zeros(len(df)), codes))
    assert len(splits) == 3
    for tr, te in splits:
        assert len(tr) > 0 and len(te) > 0
        assert set(tr).isdisjoint(set(te))
        assert len(tr) + len(te) == len(df)


# ---------------------------------------------------------------------------
# temporal_split
# ---------------------------------------------------------------------------


def _temporal_frame(n: int = 2000, seed: int = 5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    # Shuffle the input rows deliberately so a sort-preserving split is tested.
    days = rng.integers(0, 365, size=n)
    vals = rng.normal(size=n)
    perm = rng.permutation(n)
    df = pd.DataFrame({"day": days[perm], "value": vals[perm], "row_id": np.arange(n)})
    return df


def test_temporal_split_test_size_float_sum_and_order() -> None:
    df = _temporal_frame()
    train, test = temporal_split(df, "day", test_size=0.25)
    assert len(test) >= 500
    assert len(train) + len(test) == len(df)
    assert set(train).isdisjoint(set(test))
    assert set(train) | set(test) == set(range(len(df)))
    train_days = df["day"].to_numpy()[train]
    test_days = df["day"].to_numpy()[test]
    assert train_days.max() <= test_days.min()


def test_temporal_split_test_size_int_count() -> None:
    df = _temporal_frame()
    train, test = temporal_split(df, "day", test_size=300)
    assert len(test) >= 300
    assert len(train) + len(test) == len(df)
    train_days = df["day"].to_numpy()[train]
    test_days = df["day"].to_numpy()[test]
    assert train_days.max() <= test_days.min()


def test_temporal_split_cutoff_partition() -> None:
    df = _temporal_frame()
    train, test = temporal_split(df, "day", cutoff=200)
    train_days = df["day"].to_numpy()[train]
    test_days = df["day"].to_numpy()[test]
    assert np.all(train_days <= 200)
    assert np.all(test_days > 200)
    assert len(train) + len(test) == len(df)


def test_temporal_split_respects_input_order_independence() -> None:
    df_sorted = _temporal_frame().sort_values("day").reset_index(drop=True)
    df_shuffled = _temporal_frame().sample(frac=1.0, random_state=99).reset_index(drop=True)
    for df in (df_sorted, df_shuffled):
        train, test = temporal_split(df, "day", test_size=0.2)
        # Both pieces must obey ascending-time ordering regardless of input order.
        train_days = df["day"].to_numpy()[train]
        test_days = df["day"].to_numpy()[test]
        assert train_days.max() <= test_days.min()


def test_temporal_split_requires_exactly_one_arg() -> None:
    df = _temporal_frame()
    with pytest.raises(ValueError, match="exactly one"):
        temporal_split(df, "day")
    with pytest.raises(ValueError, match="exactly one"):
        temporal_split(df, "day", test_size=0.2, cutoff=100)


def test_temporal_split_invalid_test_size_float() -> None:
    df = _temporal_frame()
    with pytest.raises(ValueError, match="must be in"):
        temporal_split(df, "day", test_size=0.0)
    with pytest.raises(ValueError, match="must be in"):
        temporal_split(df, "day", test_size=1.0)


def test_temporal_split_too_large_test_count() -> None:
    df = _temporal_frame()
    with pytest.raises(ValueError, match="1.."):
        temporal_split(df, "day", test_size=len(df))
    with pytest.raises(ValueError, match="1.."):
        temporal_split(df, "day", test_size=0)


def test_temporal_split_missing_time_col_raises() -> None:
    df = _temporal_frame()
    with pytest.raises(ValueError, match="`time_col`"):
        temporal_split(df, "missing_col", test_size=0.2)


def test_temporal_split_keeps_equal_timestamps_on_one_side() -> None:
    df = pd.DataFrame({"time": [1, 2, 2, 2, 3], "value": range(5)})
    train, test = temporal_split(df, "time", test_size=2)
    assert df.iloc[train]["time"].tolist() == [1]
    assert df.iloc[test]["time"].tolist() == [2, 2, 2, 3]


def test_temporal_split_rejects_missing_times_and_empty_cutoff_partitions() -> None:
    with pytest.raises(ValueError, match="missing"):
        temporal_split(pd.DataFrame({"time": [1.0, np.nan, 2.0]}), "time", test_size=1)

    df = pd.DataFrame({"time": [1, 2, 3]})
    with pytest.raises(ValueError, match="empty"):
        temporal_split(df, "time", cutoff=0)
    with pytest.raises(ValueError, match="empty"):
        temporal_split(df, "time", cutoff=3)
