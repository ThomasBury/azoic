"""Tests for riskforge.preprocessing: AutoBinner, AutoGrouper.

Covers functional behaviour (mapping_, set_mapping round-trip, strategies,
credibility floors) and scikit-learn estimator conformance via
`parametrize_with_checks`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.utils.estimator_checks import parametrize_with_checks

from riskforge.preprocessing import AutoBinner, AutoGrouper
from tests.conftest import make_synthetic_portfolio


@parametrize_with_checks([AutoBinner(), AutoGrouper()])
def test_sklearn_compatible(estimator, check):
    check(estimator)


def _df(seed: int = 0, n: int = 4000) -> pd.DataFrame:
    return make_synthetic_portfolio(n=n, seed=seed)


# ---------------------------------------------------------------------------
# AutoBinner
# ---------------------------------------------------------------------------


def test_autobinner_quantile_bins_numeric_only() -> None:
    df = _df()
    binner = AutoBinner(cols=["driver_age", "vehicle_age"], max_bins=5).fit(df)
    out = binner.transform(df)
    assert set(binner.bin_cols_) == {"driver_age", "vehicle_age"}
    for col in ("driver_age", "vehicle_age"):
        n_bins_out = out[col].nunique()
        assert n_bins_out <= 5
        assert n_bins_out >= 1
        assert binner.mapping_[col].ndim == 1
    # non-target columns untouched
    pd.testing.assert_series_equal(out["region"], df["region"], check_names=True)


def test_autobinner_weighted_quantile_uses_exposure() -> None:
    df = _df()
    binner = AutoBinner(cols=["driver_age"], max_bins=6, exposure_col="exposure").fit(df)
    # weighted edges present and sorted
    edges = binner.mapping_["driver_age"]
    assert np.all(np.diff(edges) > 0)


def test_autobinner_tree_strategy_targets_pure_premium() -> None:
    df = _df()
    binner = AutoBinner(
        cols=["driver_age"],
        strategy="tree",
        max_bins=5,
        exposure_col="exposure",
        claim_count_col="claim_count",
        target_col="claim_amount",
        min_claims=30,
    ).fit(df)
    edges = binner.mapping_["driver_age"]
    assert len(edges) <= 4
    assert np.all(np.diff(edges) > 0)


def test_autobinner_min_exposure_merges_small_bins() -> None:
    df = _df()
    big_floor = 500.0
    binner = AutoBinner(
        cols=["driver_age"], max_bins=10, min_exposure=big_floor, exposure_col="exposure"
    ).fit(df)
    # post-merge, every bin must meet the floor
    edges = binner.mapping_["driver_age"]
    codes = np.searchsorted(edges, df["driver_age"].to_numpy(), side="right")
    exp_per = np.bincount(codes, weights=df["exposure"].to_numpy(), minlength=len(edges) + 1)
    assert (exp_per >= big_floor - 1e-9).all()


def test_autobinner_set_mapping_roundtrip() -> None:
    df = _df()
    custom = {"driver_age": np.array([25.0, 45.0, 65.0])}
    binner = AutoBinner(cols=["driver_age"]).fit(df)
    binner.set_mapping(custom)
    assert np.allclose(binner.mapping_["driver_age"], custom["driver_age"])
    out = binner.transform(df)
    assert out["driver_age"].nunique() <= 4
    labels = sorted(str(lbl) for lbl in out["driver_age"].unique())
    assert any("(-inf, 25]" in lbl for lbl in labels)


def test_autobinner_ndarray_input_returns_codes() -> None:
    X = np.column_stack([np.linspace(0, 100, 500), np.linspace(0, 1, 500)])
    binner = AutoBinner(max_bins=4).fit(X)
    out = binner.transform(X)
    assert out.shape == X.shape
    assert pd.api.types.is_numeric_dtype(pd.Series(out[:, 0]))


def test_autobinner_handles_nan() -> None:
    df = _df()
    df.loc[df.index[:50], "driver_age"] = np.nan
    binner = AutoBinner(cols=["driver_age"], max_bins=5).fit(df)
    out = binner.transform(df)
    assert out["driver_age"].isna().sum() == 0  # NaN -> last bin label


def _weighted_bin_means(df: pd.DataFrame, col: str, edges: np.ndarray) -> np.ndarray:
    codes = np.searchsorted(edges, df[col].to_numpy(), side="right")
    w = df["exposure"].to_numpy()
    tgt = df["claim_amount"].to_numpy() / df["exposure"].to_numpy()
    n_bins = len(edges) + 1
    tgt_sum = np.bincount(codes, weights=tgt * w, minlength=n_bins)
    w_sum = np.bincount(codes, weights=w, minlength=n_bins)
    means = np.where(w_sum > 0, tgt_sum / np.maximum(w_sum, 1e-12), 0.0)
    means[w_sum == 0] = 0.0
    return means


def test_autobinner_monotonic_increasing_merges_non_monotonic_bins() -> None:
    df = _df()
    binner = AutoBinner(
        cols=["driver_age"],
        strategy="tree",
        monotonic=True,
        max_bins=8,
        exposure_col="exposure",
        claim_count_col="claim_count",
        target_col="claim_amount",
    ).fit(df)
    edges = binner.mapping_["driver_age"]
    assert len(edges) >= 1
    means = _weighted_bin_means(df, "driver_age", edges)
    assert np.all(np.diff(means) >= -1e-9)


def test_autobinner_monotonic_decreasing_enforces_non_increasing() -> None:
    df = _df()
    binner = AutoBinner(
        cols=["vehicle_age"],
        strategy="tree",
        monotonic="decreasing",
        max_bins=8,
        exposure_col="exposure",
        claim_count_col="claim_count",
        target_col="claim_amount",
    ).fit(df)
    edges = binner.mapping_["vehicle_age"]
    if len(edges) >= 1:
        means = _weighted_bin_means(df, "vehicle_age", edges)
        assert np.all(np.diff(means) <= 1e-9)


def test_autobinner_monotonic_false_default_unchanged() -> None:
    df = _df()
    b_off = AutoBinner(
        cols=["driver_age"],
        strategy="tree",
        max_bins=8,
        exposure_col="exposure",
        claim_count_col="claim_count",
        target_col="claim_amount",
    ).fit(df)
    b_default = AutoBinner(
        cols=["driver_age"],
        strategy="tree",
        max_bins=8,
        exposure_col="exposure",
        claim_count_col="claim_count",
        target_col="claim_amount",
        monotonic=False,
    ).fit(df)
    np.testing.assert_array_equal(b_off.mapping_["driver_age"], b_default.mapping_["driver_age"])


def test_autobinner_monotonic_no_target_is_noop() -> None:
    df = _df()
    binner = AutoBinner(
        cols=["driver_age"], strategy="quantile", max_bins=6, monotonic=True
    ).fit(df)
    edges = binner.mapping_["driver_age"]
    assert len(edges) >= 1  # just runs the standard quantile path


def test_autobinner_monotonic_invalid_value_raises_at_fit() -> None:
    df = _df()
    binner = AutoBinner(
        cols=["driver_age"],
        strategy="tree",
        monotonic="bogus",
        exposure_col="exposure",
        claim_count_col="claim_count",
        target_col="claim_amount",
    )
    with pytest.raises(ValueError, match="monotonic"):
        binner.fit(df)


# ---------------------------------------------------------------------------
# AutoGrouper
# ---------------------------------------------------------------------------


def test_autogrouper_default_cols_are_non_numeric() -> None:
    df = _df()
    grouper = AutoGrouper(exposure_col="exposure", min_exposure=200.0).fit(df)
    assert set(grouper.group_cols_) == {"region", "vehicle_brand"}


def test_autogrouper_rare_merges_small_levels() -> None:
    df = _df()
    grouper = AutoGrouper(
        cols=["region"], strategy="rare", min_exposure=10_000.0, exposure_col="exposure"
    ).fit(df)
    mp = grouper.mapping_["region"]
    small_levels = [lvl for lvl, grp in mp.items() if grp == "Other"]
    assert len(small_levels) >= 1


def test_autogrouper_similarity_groups_meet_floor() -> None:
    df = _df()
    floor = 300.0
    grouper = AutoGrouper(
        cols=["vehicle_brand"],
        strategy="similarity",
        min_exposure=floor,
        max_groups=4,
        exposure_col="exposure",
        target_col="claim_amount",
    ).fit(df)
    mp = grouper.mapping_["vehicle_brand"]
    groups = {}
    for lvl, grp in mp.items():
        groups.setdefault(grp, []).append(lvl)
    grouper.transform(df)  # sanity: mapping is applicable
    for _label, levels in groups.items():
        mask = df["vehicle_brand"].isin(levels)
        assert df.loc[mask, "exposure"].sum() >= floor
    # max_groups respected
    assert len(groups) <= 4


def test_autogrouper_set_mapping_roundtrip() -> None:
    df = _df()
    custom = {"region": {"urban": "urban", "suburban": "urban", "rural": "rural"}}
    grouper = AutoGrouper(cols=["region"]).fit(df)
    grouper.set_mapping(custom)
    out = grouper.transform(df)
    assert set(out["region"].unique()) == {"urban", "rural"}


def test_autogrouper_unknown_level_to_other() -> None:
    df = _df()
    grouper = AutoGrouper(cols=["region"], strategy="rare", min_exposure=0.0).fit(df)
    cols = list(df.columns)
    unseen = pd.concat([df.iloc[:2].copy(), pd.DataFrame({"region": ["mars"]}, index=[2])])
    unseen = unseen[cols].iloc[[2]]  # same columns as fit, only the unseen row
    out = grouper.transform(unseen)
    assert out["region"].iloc[0] == "Other"


def test_autogrouper_preserves_other_columns() -> None:
    df = _df()
    grouper = AutoGrouper(cols=["region"]).fit(df)
    out = grouper.transform(df)
    pd.testing.assert_series_equal(out["vehicle_brand"], df["vehicle_brand"], check_names=True)
