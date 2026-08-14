"""Tests for azoic.preprocessing: AutoBinner, AutoGrouper.

Covers functional behaviour (mapping_, set_mapping round-trip, strategies,
credibility floors) and scikit-learn estimator conformance via
`parametrize_with_checks`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.pipeline import Pipeline
from sklearn.utils.estimator_checks import parametrize_with_checks

from azoic.models import RiskGLM
from azoic.preprocessing import AutoBinner, AutoGrouper, _merge_small_bins
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


def test_merge_small_bins_matches_rebinning_algorithm() -> None:
    rng = np.random.default_rng(42)
    values = rng.normal(size=2000)
    weights = rng.uniform(0.1, 2.0, size=len(values))
    original = np.quantile(values, np.linspace(0, 1, 21)[1:-1])

    edges = list(original)
    while edges:
        codes = np.searchsorted(np.asarray(edges), values, side="right")
        bin_weights = np.bincount(codes, weights=weights, minlength=len(edges) + 1)
        small = np.flatnonzero(bin_weights < 150.0)
        if len(small) == 0:
            break
        index = int(small[0])
        edges.pop(0 if index == 0 else -1 if index >= len(edges) else index)

    np.testing.assert_array_equal(
        _merge_small_bins(values, weights, original, 150.0),
        np.asarray(edges),
    )


def test_autobinner_set_mapping_roundtrip() -> None:
    df = _df()
    custom = {"driver_age": np.array([25.0, 45.0, 65.0])}
    binner = AutoBinner(cols=["driver_age"]).fit(df)
    binner.set_mapping(custom)
    assert np.allclose(binner.mapping_["driver_age"], custom["driver_age"])
    out = binner.transform(df)
    assert out["driver_age"].nunique() <= 4
    assert "(-inf, 25.0]" in out["driver_age"].cat.categories


def test_autobinner_reserves_ordered_interval_vocabulary() -> None:
    df = pd.DataFrame({"x": [0.0, 1.0, 2.0, 3.0]})
    binner = AutoBinner(cols=["x"], max_bins=2).fit(df)

    out = binner.transform(df.iloc[[0]])

    assert out["x"].dtype == binner.category_dtypes_["x"]
    assert out["x"].cat.ordered
    assert len(out["x"].cat.categories) == len(binner.mapping_["x"]) + 2
    assert (
        list(out["x"].cat.categories)
        == binner._labels(np.arange(len(binner.mapping_["x"]) + 2), binner.mapping_["x"]).tolist()
    )
    assert out["x"].cat.categories[-1] == "Missing"


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
    assert out["driver_age"].isna().sum() == 0
    assert set(out.loc[df["driver_age"].isna(), "driver_age"]) == {"Missing"}
    assert "Missing" not in set(out.loc[df["driver_age"].notna(), "driver_age"])


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
    binner = AutoBinner(cols=["driver_age"], strategy="quantile", max_bins=6, monotonic=True).fit(
        df
    )
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
    assert list(out["region"].cat.categories) == ["urban", "rural", "Other"]


def test_autogrouper_unknown_level_to_other() -> None:
    df = _df()
    grouper = AutoGrouper(cols=["region"], strategy="rare", min_exposure=0.0).fit(df)
    cols = list(df.columns)
    unseen = pd.concat([df.iloc[:2].copy(), pd.DataFrame({"region": ["mars"]}, index=[2])])
    unseen = unseen[cols].iloc[[2]]  # same columns as fit, only the unseen row
    with pytest.warns(UserWarning, match="region=.*mars"):
        out = grouper.transform(unseen)
    assert out["region"].iloc[0] == "Other"
    assert out["region"].dtype == grouper.category_dtypes_["region"]


def test_autogrouper_aggregates_unseen_warnings_and_silently_groups_missing() -> None:
    train = pd.DataFrame({"first": ["A", "B"], "second": ["X", "Y"]})
    grouper = AutoGrouper(cols=["first", "second"], strategy="rare", min_exposure=0.0).fit(train)

    with pytest.warns(UserWarning) as caught:
        out = grouper.transform(pd.DataFrame({"first": ["new-a", None], "second": ["new-b", None]}))

    assert len(caught) == 1
    message = str(caught[0].message)
    assert "first=['new-a']" in message
    assert "second=['new-b']" in message
    assert "None" not in message
    assert (out.iloc[1] == "Other").all()
    assert all(out[col].cat.categories[-1] == "Other" for col in out)


def test_autogrouper_ordered_similarity_merges_only_adjacent_levels() -> None:
    levels = ["A", "B", "C", "D"]
    df = pd.DataFrame(
        {
            "segment": pd.Series(levels, dtype=pd.CategoricalDtype(levels, ordered=True)),
            "exposure": [10.0, 1.0, 10.0, 10.0],
            "claim_amount": [0.0, 1.0, 20.0, 1_000.0],
        }
    )
    grouper = AutoGrouper(
        cols=["segment"],
        strategy="similarity",
        min_exposure=5.0,
        max_groups=2,
        exposure_col="exposure",
        target_col="claim_amount",
    ).fit(df)

    mapping = grouper.mapping_["segment"]
    assert mapping["A"] == mapping["B"] == mapping["C"]
    assert mapping["C"] != mapping["D"]
    out = grouper.transform(df)
    assert out["segment"].cat.ordered
    assert list(out["segment"].cat.categories) == [mapping["A"], "D", "Other"]


def test_autogrouper_nominal_similarity_vocabulary_follows_risk() -> None:
    df = pd.DataFrame(
        {
            "segment": ["A", "B", "C"],
            "exposure": [10.0, 10.0, 10.0],
            "claim_amount": [20.0, 0.0, 10.0],
        }
    )
    grouper = AutoGrouper(
        cols=["segment"],
        strategy="similarity",
        exposure_col="exposure",
        target_col="claim_amount",
    ).fit(df)

    assert list(grouper.category_dtypes_["segment"].categories) == ["B", "C", "A", "Other"]
    assert not grouper.category_dtypes_["segment"].ordered


def test_autogrouper_set_mapping_rebuilds_ordered_vocabulary() -> None:
    dtype = pd.CategoricalDtype(["A", "B", "C"], ordered=True)
    grouper = AutoGrouper(cols=["segment"]).fit(
        pd.DataFrame({"segment": pd.Series(["A", "B", "C"], dtype=dtype)})
    )

    grouper.set_mapping({"segment": {"B": "second", "A": "first", "C": "second"}})

    fitted = grouper.category_dtypes_["segment"]
    assert fitted.ordered
    assert list(fitted.categories) == ["second", "first", "Other"]


def test_autogrouper_reserved_other_supports_glm_prediction() -> None:
    X = pd.DataFrame({"segment": ["A", "B", "A", "B"]})
    model = Pipeline(
        [
            (
                "grouper",
                AutoGrouper(cols=["segment"], strategy="rare", min_exposure=0.0),
            ),
            ("model", RiskGLM()),
        ]
    ).fit(X, np.array([1.0, 2.0, 1.5, 2.5]))

    with pytest.warns(UserWarning, match="segment=.*unseen"):
        prediction = model.predict(pd.DataFrame({"segment": ["unseen"]}))

    assert np.isfinite(prediction).all()


def test_autogrouper_preserves_other_columns() -> None:
    df = _df()
    grouper = AutoGrouper(cols=["region"]).fit(df)
    out = grouper.transform(df)
    pd.testing.assert_series_equal(out["vehicle_brand"], df["vehicle_brand"], check_names=True)


def test_supervised_preprocessors_exclude_and_reject_special_columns() -> None:
    df = _df(n=500)
    binner = AutoBinner(
        exposure_col="exposure",
        claim_count_col="claim_count",
        target_col="claim_amount",
    ).fit(df)
    grouper = AutoGrouper(
        exposure_col="exposure",
        claim_count_col="claim_count",
        target_col="claim_amount",
    ).fit(df)

    specials = {"exposure", "claim_count", "claim_amount"}
    assert specials.isdisjoint(binner.bin_cols_)
    assert specials.isdisjoint(grouper.group_cols_)
    with pytest.raises(ValueError, match="special"):
        AutoBinner(cols=["exposure"], exposure_col="exposure").fit(df)
    with pytest.raises(ValueError, match="special"):
        AutoGrouper(cols=["claim_amount"], target_col="claim_amount").fit(df)


def test_autogrouper_relativities_use_aggregate_claims_over_exposure() -> None:
    df = pd.DataFrame(
        {
            "segment": ["A", "A", "B", "B"],
            "exposure": [1.0, 9.0, 1.0, 9.0],
            "claim_amount": [10.0, 0.0, 0.0, 20.0],
        }
    )
    grouper = AutoGrouper(
        cols=["segment"],
        exposure_col="exposure",
        target_col="claim_amount",
    ).fit(df)
    stats = grouper._level_stats(
        df["segment"].to_numpy(),
        df["exposure"].to_numpy(),
        None,
        df["claim_amount"].to_numpy(),
    )
    assert stats.loc["A", "pp"] == pytest.approx(1.0)
    assert stats.loc["B", "pp"] == pytest.approx(2.0)


def test_autobinner_min_claims_uses_aggregate_claim_count_per_bin() -> None:
    df = pd.DataFrame(
        {
            "x": np.arange(20, dtype=float),
            "exposure": np.ones(20),
            "claim_count": np.r_[np.zeros(10), np.ones(10)],
            "claim_amount": np.r_[np.zeros(10), np.arange(1.0, 11.0)],
        }
    )
    binner = AutoBinner(
        cols=["x"],
        strategy="tree",
        max_bins=6,
        min_claims=3,
        exposure_col="exposure",
        claim_count_col="claim_count",
        target_col="claim_amount",
    ).fit(df)
    edges = binner.mapping_["x"]
    codes = np.searchsorted(edges, df["x"].to_numpy(), side="right")
    counts = np.bincount(
        codes,
        weights=df["claim_count"].to_numpy(),
        minlength=len(edges) + 1,
    )
    assert (counts >= 3).all()


def test_autogrouper_merges_trailing_group_below_credibility_floor() -> None:
    df = pd.DataFrame(
        {
            "segment": ["A", "B", "C"],
            "exposure": [10.0, 10.0, 1.0],
            "claim_amount": [10.0, 20.0, 3.0],
        }
    )
    grouper = AutoGrouper(
        cols=["segment"],
        strategy="similarity",
        min_exposure=10.0,
        exposure_col="exposure",
        target_col="claim_amount",
    ).fit(df)
    mapping = grouper.mapping_["segment"]
    assert mapping["B"] == mapping["C"]
