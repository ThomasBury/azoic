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

from azoic.data import MIN_EXPOSURE
from azoic.models import RiskGLM
from azoic.preprocessing import AutoBinner, AutoGrouper, _merge_small_bins
from tests.conftest import make_synthetic_portfolio


@parametrize_with_checks([AutoBinner(), AutoGrouper()])
def test_sklearn_compatible(estimator, check):
    check(estimator)


@pytest.mark.parametrize("cls", [AutoBinner, AutoGrouper])
@pytest.mark.parametrize("column", ["exposure", "claim_count"])
@pytest.mark.parametrize("value", [None, -1.0, np.nan, np.inf, "bad"])
def test_preprocessing_rejects_invalid_configured_weights(cls, column, value) -> None:
    df = pd.DataFrame({"x": [0.0, 1.0, 2.0], "exposure": [1.0] * 3, "claim_count": [1.0] * 3})
    if value is None:
        df = df.drop(columns=column)
    else:
        df[column] = [value, 1.0, 1.0]
    transformer = cls(cols=["x"], exposure_col="exposure", claim_count_col="claim_count")
    with pytest.raises(ValueError):
        transformer.fit(df, [0.0, 1.0, 2.0])


@pytest.mark.parametrize("cls", [AutoBinner, AutoGrouper])
@pytest.mark.parametrize("exposure", [0.0, MIN_EXPOSURE / 2])
def test_preprocessing_rejects_subday_exposure(cls, exposure) -> None:
    df = pd.DataFrame({"x": [0.0, 1.0], "exposure": [exposure, 1.0]})
    with pytest.raises(ValueError, match="1/366"):
        cls(cols=["x"], exposure_col="exposure").fit(df, [1.0, 2.0])


@pytest.mark.parametrize("strategy", ["quantile", "tree"])
@pytest.mark.parametrize("max_bins", [0, 1, -1, 2.5, 2.0, True, None])
def test_autobinner_rejects_invalid_bin_counts(strategy, max_bins) -> None:
    with pytest.raises(ValueError, match="max_bins"):
        AutoBinner(strategy=strategy, max_bins=max_bins).fit(
            pd.DataFrame({"x": [0.0, 1.0, 2.0]}), [1.0, 2.0, 3.0]
        )


@pytest.mark.parametrize("edges", [[2, 1], [1, 1], [np.nan], [np.inf], [[1, 2]]])
def test_autobinner_invalid_mapping_preserves_state(edges) -> None:
    df = pd.DataFrame({"x": [0.0, 1.0, 2.0], "z": [1.0, 2.0, 3.0]})
    binner = AutoBinner(cols=["x", "z"]).fit(df)
    before = binner.transform(df)
    mapping, dtypes, columns = binner.mapping_, binner.category_dtypes_, binner.bin_cols_
    with pytest.raises(ValueError):
        binner.set_mapping({"x": [0.5], "z": edges})
    assert binner.mapping_ is mapping
    assert binner.category_dtypes_ is dtypes
    assert binner.bin_cols_ is columns
    pd.testing.assert_frame_equal(binner.transform(df), before)


@pytest.mark.parametrize("cls", [AutoBinner, AutoGrouper])
@pytest.mark.parametrize("column", ["unknown", "exposure", "unselected"])
def test_preprocessing_mapping_rejects_unfitted_columns(cls, column) -> None:
    df = pd.DataFrame({"x": [0, 1, 2], "unselected": [3, 4, 5], "exposure": [1.0] * 3})
    transformer = cls(cols=["x"], exposure_col="exposure").fit(df, [1, 2, 3])
    before = transformer.transform(df)
    values = [1.0] if cls is AutoBinner else {0: "zero"}
    with pytest.raises(ValueError, match=column):
        transformer.set_mapping({column: values})
    pd.testing.assert_frame_equal(transformer.transform(df), before)


def test_autogrouper_invalid_vocabulary_preserves_state() -> None:
    df = pd.DataFrame({"x": ["A", "B"], "z": ["C", "D"]})
    grouper = AutoGrouper(strategy="rare").fit(df)
    before = grouper.transform(df)
    mapping, dtypes, columns = grouper.mapping_, grouper.category_dtypes_, grouper.group_cols_
    with pytest.raises(ValueError):
        grouper.set_mapping({"x": {"A": "new"}, "z": {"C": None}})
    assert grouper.mapping_ is mapping
    assert grouper.category_dtypes_ is dtypes
    assert grouper.group_cols_ is columns
    pd.testing.assert_frame_equal(grouper.transform(df), before)


@pytest.mark.parametrize("cls", [AutoBinner, AutoGrouper])
def test_preprocessing_mapping_replaces_selected_columns(cls) -> None:
    df = pd.DataFrame({"x": [0, 1, 2], "z": [3, 4, 5]})
    transformer = cls(cols=["x", "z"]).fit(df, [1, 2, 3])
    values = [] if cls is AutoBinner else {0: 10, 1: 10, 2: 20}
    transformer.set_mapping({"x": values})
    out = transformer.transform(df)
    assert list(transformer.mapping_) == ["x"]
    pd.testing.assert_series_equal(out["z"], df["z"])
    assert out["x"].cat.categories[-1] == ("Missing" if cls is AutoBinner else "Other")


@pytest.mark.parametrize("cls", [AutoBinner, AutoGrouper])
def test_preprocessing_preserves_target_fallback_and_exposure_units(cls) -> None:
    df = pd.DataFrame(
        {
            "x": [0, 1, 2, 3],
            "exposure": [MIN_EXPOSURE * (1 - 5e-4), 9.0, 1.0, 9.0],
            "claim_count": [0.0, 1.0, 0.0, 2.0],
        }
    )
    rates = np.array([1.0, 2.0, 10.0, 11.0])
    df["amount"] = rates * df["exposure"]
    kwargs = {"strategy": "tree", "max_bins": np.int64(2)} if cls is AutoBinner else {}
    params = dict(cols=["x"], exposure_col="exposure", claim_count_col="claim_count", **kwargs)
    aggregate = cls(target_col="amount", **params).fit(df)
    fallback = cls(target_col="absent", **params).fit(df, rates)
    pd.testing.assert_frame_equal(aggregate.transform(df), fallback.transform(df))
    cls(cols=["x"], **kwargs).fit(df[["x"]], rates).transform(df[["x"]])


@pytest.mark.parametrize("cls", [AutoBinner, AutoGrouper])
@pytest.mark.parametrize("source", ["y", "target_col"])
@pytest.mark.parametrize(
    "outcomes",
    [
        [np.nan, 0.0, 10.0, 10.0],
        [np.nan, np.nan, 10.0, 10.0],
        [np.nan] * 4,
        [np.inf, 0.0, 10.0, 10.0],
        [-np.inf, 0.0, 10.0, 10.0],
        ["nan", "0", "10", "10"],
        ["inf", "0", "10", "10"],
        ["-inf", "0", "10", "10"],
        pd.Series([pd.NA, 0.0, 10.0, 10.0], dtype="Float64"),
        pd.Series([pd.NA] * 4, dtype="Float64"),
    ],
)
def test_preprocessing_rejects_nonfinite_outcomes(cls, source, outcomes) -> None:
    df = pd.DataFrame({"x": [0, 0, 1, 1], "exposure": [1.0, 3.0, 1.0, 3.0]})
    kwargs = {"strategy": "tree", "max_bins": 2} if cls is AutoBinner else {}
    if source == "target_col":
        df["amount"] = outcomes
        kwargs["target_col"] = "amount"
        y = [1.0, 2.0, 3.0, 4.0]
    else:
        y = outcomes
    with pytest.raises(ValueError, match="NaN|infinity"):
        cls(cols=["x"], exposure_col="exposure", **kwargs).fit(df, y)


@pytest.mark.parametrize("cls", [AutoBinner, AutoGrouper])
def test_preprocessing_validates_outcomes_before_masking_predictors(cls) -> None:
    df = pd.DataFrame({"x": [np.nan, 1.0, 2.0], "amount": [np.nan, 0.0, 10.0]})
    kwargs = {"strategy": "tree", "max_bins": 2} if cls is AutoBinner else {}
    with pytest.raises(ValueError, match="NaN"):
        cls(cols=["x"], target_col="amount", **kwargs).fit(df)


@pytest.mark.parametrize("cls", [AutoBinner, AutoGrouper])
def test_preprocessing_rejects_outcome_unit_conversion_overflow(cls) -> None:
    df = pd.DataFrame({"x": [0, 1, 2], "exposure": [2.0] * 3})
    kwargs = {}
    y = [1e308, 1.0, 2.0]
    if cls is AutoBinner:
        df["exposure"] = 0.5
        df["amount"] = y
        kwargs["target_col"] = "amount"
        y = None
    with np.errstate(over="ignore"), pytest.raises(ValueError, match="infinity"):
        cls(cols=["x"], exposure_col="exposure", **kwargs).fit(df, y)


@pytest.mark.parametrize("cls", [AutoBinner, AutoGrouper])
@pytest.mark.parametrize("fit_dataframe", [True, False])
def test_preprocessing_rejects_unmatched_transform_columns(cls, fit_dataframe) -> None:
    frame = pd.DataFrame({"age": [10.0, 20.0, 30.0, 40.0]})
    train, probe = (frame, frame.to_numpy()) if fit_dataframe else (frame.to_numpy(), frame)
    column = "age" if fit_dataframe else "x0"
    kwargs = {"max_bins": 2} if cls is AutoBinner else {"max_groups": 2}
    transformer = cls(cols=[column], **kwargs).fit(train, [1.0, 1.0, 9.0, 9.0])
    with (
        pytest.warns(UserWarning, match="feature names"),
        pytest.raises(ValueError, match=f"missing fitted mapping columns.*{column}"),
    ):
        transformer.transform(probe)


@pytest.mark.parametrize("cls", [AutoBinner, AutoGrouper])
@pytest.mark.parametrize("dataframe", [True, False])
def test_preprocessing_same_representation_applies_mapping(cls, dataframe) -> None:
    frame = pd.DataFrame({"age": [10.0, 20.0, 30.0, 40.0], "other": [5.0] * 4})
    X = frame if dataframe else frame.to_numpy()
    column = "age" if dataframe else "x0"
    kwargs = {"max_bins": 2} if cls is AutoBinner else {"max_groups": 2}
    transformer = cls(cols=[column], **kwargs).fit(X, [1.0, 1.0, 9.0, 9.0])
    out = transformer.transform(X)
    if dataframe:
        actual = out[column].cat.codes if cls is AutoBinner else out[column]
        pd.testing.assert_series_equal(out["other"], frame["other"])
        assert out[column].dtype == transformer.category_dtypes_[column]
    else:
        actual = out[:, 0]
        np.testing.assert_array_equal(out[:, 1], X[:, 1])
    expected = [0, 0, 1, 1] if cls is AutoBinner else ["group_0"] * 2 + ["group_1"] * 2
    assert list(actual) == expected


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


def test_autobinner_quantiles_ignore_missing_exposure() -> None:
    observed = pd.DataFrame({"value": [10, 20, 20, 30, 40, 50], "exposure": [1, 2, 3, 1, 2, 1]})
    extended = pd.concat(
        [observed, pd.DataFrame({"value": [np.nan], "exposure": [1e9]})], ignore_index=True
    )
    baseline = AutoBinner(cols=["value"], max_bins=3, exposure_col="exposure").fit(observed)
    binner = AutoBinner(cols=["value"], max_bins=3, exposure_col="exposure").fit(extended)
    np.testing.assert_array_equal(baseline.mapping_["value"], [20, 30])
    np.testing.assert_array_equal(binner.mapping_["value"], baseline.mapping_["value"])
    pd.testing.assert_frame_equal(binner.transform(observed), baseline.transform(observed))
    assert binner.transform(extended)["value"].iloc[-1] == "Missing"


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


def test_merge_small_bins_merges_the_last_two_bins() -> None:
    np.testing.assert_array_equal(
        _merge_small_bins(np.array([0.0, 1.0]), np.array([200.0, 50.0]), np.array([0.5]), 150),
        np.array([]),
    )


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
    assert "(-inf, 25.0)" in out["driver_age"].cat.categories


@pytest.mark.parametrize(
    ("training", "edges", "labels"),
    [
        ([np.nan, np.nan], [], ["(-inf, inf)"]),
        ([0.0, 60.0], [30.0], ["(-inf, 30.0)", "[30.0, inf)"]),
        (
            [0.0, 30.0, 60.0, 90.0],
            [30.0, 60.0],
            ["(-inf, 30.0)", "[30.0, 60.0)", "[60.0, inf)"],
        ),
    ],
)
def test_autobinner_interval_boundaries_and_mapping_roundtrip(training, edges, labels) -> None:
    binner = AutoBinner(cols=["x"], max_bins=max(2, len(edges) + 1)).fit(
        pd.DataFrame({"x": training})
    )
    np.testing.assert_array_equal(binner.mapping_["x"], edges)
    values, expected = [-1e6], [labels[0]]
    for i, edge in enumerate(edges):
        values.extend([np.nextafter(edge, -np.inf), edge, np.nextafter(edge, np.inf)])
        expected.extend([labels[i], labels[i + 1], labels[i + 1]])
    values.extend([1e6, np.nan])
    expected.extend([labels[-1], "Missing"])
    frame = pd.DataFrame({"x": values})

    for _ in range(2):
        out = binner.transform(frame)["x"]
        assert out.tolist() == expected
        assert out.cat.categories.tolist() == [*labels, "Missing"]
        assert out.cat.ordered
        binner.set_mapping({"x": edges})


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


@pytest.mark.parametrize("direction", ["increasing", "decreasing"])
@pytest.mark.parametrize("weighted", [False, True])
@pytest.mark.parametrize("values", [[5.0] * 4, [1.0, 1.0, 2.0, 2.0]])
def test_autobinner_monotonic_handles_constant_and_tied_values(direction, weighted, values) -> None:
    df = pd.DataFrame({"x": [*values, np.nan], "exposure": [1.0, 3.0, 1.0, 3.0, 2.0]})
    y = [1.0, 1.0, 4.0, 4.0]
    if direction == "decreasing":
        y.reverse()
    binner = AutoBinner(
        cols=["x"],
        max_bins=4,
        monotonic=direction,
        exposure_col="exposure" if weighted else None,
    ).fit(df, [*y, 100.0])
    expected = [] if len(set(values)) == 1 else [2.0 if weighted else 1.5]
    np.testing.assert_array_equal(binner.mapping_["x"], expected)
    out = binner.transform(df)["x"]
    assert out.cat.codes.tolist() == ([0] * 4 if not expected else [0, 0, 1, 1]) + [
        len(expected) + 1
    ]
    assert out.iloc[-1] == "Missing"


@pytest.mark.parametrize("direction", ["increasing", "decreasing"])
@pytest.mark.parametrize("pool", [False, True])
def test_autobinner_monotonic_preserves_edges_across_empty_bins(direction, pool) -> None:
    values = np.array([0.5, 0.5, 2.5, 2.5, 5.5, 5.5])
    target = np.array([3, 3, 1, 1, 5, 5] if pool else [1, 1, 3, 3, 5, 5], dtype=float)
    if direction == "decreasing":
        target = 6.0 - target
    edges = AutoBinner(monotonic=direction)._enforce_monotonic(
        np.arange(6.0), values, np.array([1.0, 2.0] * 3), target
    )
    np.testing.assert_array_equal(edges, [3.0] if pool else [1.0, 3.0])
    codes = np.searchsorted(edges, values, side="right")
    assert codes.tolist() == ([0, 0, 0, 0, 1, 1] if pool else [0, 0, 1, 1, 2, 2])


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
    grouper = AutoGrouper(
        exposure_col="exposure", target_col="claim_amount", min_exposure=200.0
    ).fit(df)
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


@pytest.mark.parametrize("rate_target", [False, True], ids=["aggregate-column", "rate-y"])
@pytest.mark.parametrize(
    ("rates", "exposures", "claims", "max_groups", "min_exposure", "min_claims", "groups"),
    [
        ([100, 101, 10000], [10, 10, 10], [5, 5, 5], 2, None, None, ["AB", "C"]),
        ([0, 4, 5, 8.7], [1, 9, 1, 1], [5, 5, 5, 5], 2, None, None, ["ABC", "D"]),
        ([0, 1, 2.2, 3.6], [10, 10, 10, 10], [5, 5, 5, 5], 2, None, None, ["AB", "CD"]),
        ([100, 101, 102], [10, 10, 10], [5, 5, 5], 2, None, None, ["AB", "C"]),
        ([100, 10000, 100], [10, 10, 10], [5, 5, 5], 2, None, None, ["AC", "B"]),
        ([100, 1000, 1001], [10, 1, 10], [5, 5, 5], 3, 5, None, ["A", "BC"]),
        ([100, 101, 1000], [10, 1, 10], [5, 5, 5], 3, 5, None, ["AB", "C"]),
        ([100, 101, 102], [10, 1, 10], [5, 5, 5], 3, 5, None, ["AB", "C"]),
        ([100, 1000, 1001], [10, 10, 10], [5, 1, 5], 3, None, 3, ["A", "BC"]),
        ([100, 101, 1000], [1, 1, 1], [1, 1, 1], 3, 5, 5, ["ABC"]),
    ],
    ids=[
        "closest-risk",
        "aggregate-risk",
        "recompute",
        "left-tie",
        "stable-risk-sort",
        "exposure-right",
        "exposure-left",
        "exposure-tie",
        "claim-floor",
        "impossible-floor",
    ],
)
def test_autogrouper_nominal_similarity_merges_nearest_risks(
    rate_target, rates, exposures, claims, max_groups, min_exposure, min_claims, groups
) -> None:
    levels = list("ABCD"[: len(rates)])
    df = pd.DataFrame(
        {
            "segment": levels,
            "exposure": exposures,
            "claim_count": claims,
            "claim_amount": np.multiply(rates, exposures),
        }
    )
    grouper = AutoGrouper(
        cols=["segment"],
        strategy="similarity",
        max_groups=max_groups,
        min_exposure=min_exposure,
        min_claims=min_claims,
        exposure_col="exposure",
        claim_count_col="claim_count",
        target_col=None if rate_target else "claim_amount",
    ).fit(df, rates if rate_target else None)

    mapping = grouper.mapping_["segment"]
    expected = {
        level: group[0] if len(group) == 1 else f"group_{i}"
        for i, group in enumerate(groups)
        for level in group
    }
    assert list(mapping.items()) == list(expected.items())
    out = grouper.transform(df)
    assert out["segment"].tolist() == [expected[level] for level in levels]
    assert not out["segment"].cat.ordered
    grouper.set_mapping(grouper.mapping_)
    pd.testing.assert_frame_equal(grouper.transform(df), out)


def test_autogrouper_ordered_similarity_keeps_declared_nonmonotonic_order() -> None:
    df = pd.DataFrame(
        {
            "segment": pd.Categorical(["A", "B", "C"], categories=["C", "B", "A"], ordered=True),
            "exposure": [10, 10, 10],
            "claim_amount": [1000, 100000, 1010],
        }
    )
    grouper = AutoGrouper(
        cols=["segment"], max_groups=2, exposure_col="exposure", target_col="claim_amount"
    ).fit(df)
    mapping = grouper.mapping_["segment"]
    assert list(mapping) == ["C", "B", "A"]
    assert mapping["C"] == mapping["B"] != mapping["A"]
    assert grouper.transform(df)["segment"].cat.ordered


def test_autogrouper_set_mapping_roundtrip() -> None:
    df = _df()
    custom = {"region": {"urban": "urban", "suburban": "urban", "rural": "rural"}}
    grouper = AutoGrouper(cols=["region"], target_col="claim_amount").fit(df)
    grouper.set_mapping(custom)
    out = grouper.transform(df)
    assert set(out["region"].unique()) == {"urban", "rural"}
    assert list(out["region"].cat.categories) == ["urban", "rural", "Other"]


def test_autogrouper_unknown_level_to_other() -> None:
    df = _df()
    grouper = AutoGrouper(cols=["region"], strategy="rare", min_exposure=None).fit(df)
    cols = list(df.columns)
    unseen = pd.concat([df.iloc[:2].copy(), pd.DataFrame({"region": ["mars"]}, index=[2])])
    unseen = unseen[cols].iloc[[2]]  # same columns as fit, only the unseen row
    with pytest.warns(UserWarning, match="region=.*mars"):
        out = grouper.transform(unseen)
    assert out["region"].iloc[0] == "Other"
    assert out["region"].dtype == grouper.category_dtypes_["region"]


def test_autogrouper_aggregates_unseen_warnings_and_includes_missing() -> None:
    train = pd.DataFrame({"first": ["A", "B"], "second": ["X", "Y"]})
    grouper = AutoGrouper(cols=["first", "second"], strategy="rare", min_exposure=None).fit(train)

    with pytest.warns(UserWarning) as caught:
        out = grouper.transform(pd.DataFrame({"first": ["new-a", None], "second": ["new-b", None]}))

    assert len(caught) == 1
    message = str(caught[0].message)
    assert "first=['new-a', nan]" in message
    assert "second=['new-b', nan]" in message
    assert (out.iloc[1] == "Other").all()
    assert all(out[col].cat.categories[-1] == "Other" for col in out)

    with pytest.warns(UserWarning, match=r"first=\[nan\]"):
        na_out = grouper.transform(pd.DataFrame({"first": ["A", None], "second": ["X", "Y"]}))
    assert na_out["first"].tolist() == ["A", "Other"]


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
        pd.DataFrame({"segment": pd.Series(["A", "B", "C"], dtype=dtype)}),
        [1.0, 2.0, 3.0],
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
                AutoGrouper(cols=["segment"], strategy="rare", min_exposure=None),
            ),
            ("model", RiskGLM()),
        ]
    ).fit(X, np.array([1.0, 2.0, 1.5, 2.5]))

    with pytest.warns(UserWarning, match="segment=.*unseen"):
        prediction = model.predict(pd.DataFrame({"segment": ["unseen"]}))

    assert np.isfinite(prediction).all()


def test_autogrouper_preserves_other_columns() -> None:
    df = _df()
    grouper = AutoGrouper(cols=["region"], target_col="claim_amount").fit(df)
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


# ---------------------------------------------------------------------------
# Fail-closed configuration (M32)
# ---------------------------------------------------------------------------


def test_autobinner_rejects_unknown_requested_columns() -> None:
    df = _df()
    with pytest.raises(ValueError, match=r"cols not found in X: \['driver_agee'\]"):
        AutoBinner(cols=["driver_age", "driver_agee"]).fit(df)


def test_autogrouper_rejects_unknown_requested_columns() -> None:
    df = _df()
    with pytest.raises(ValueError, match=r"cols not found in X: \['regionn'\]"):
        AutoGrouper(cols=["region", "regionn"]).fit(df)


@pytest.mark.parametrize("strategy", ["quantilee", "trees", ""])
def test_autobinner_rejects_unknown_strategy(strategy: str) -> None:
    with pytest.raises(ValueError, match="strategy must be 'quantile' or 'tree'"):
        AutoBinner(strategy=strategy).fit(_df())


@pytest.mark.parametrize("strategy", ["simmilarity", "raree", ""])
def test_autogrouper_rejects_unknown_strategy(strategy: str) -> None:
    with pytest.raises(ValueError, match="strategy must be 'rare' or 'similarity'"):
        AutoGrouper(strategy=strategy).fit(_df())


def test_autogrouper_similarity_requires_a_target() -> None:
    """Without a target every level has risk zero and merges in incidental
    order; that must raise, not silently group. rare is floor-based and
    needs no target."""
    df = _df()[["region"]]
    with pytest.raises(ValueError, match="similarity grouping requires a target"):
        AutoGrouper(cols=["region"], strategy="similarity").fit(df)
    AutoGrouper(cols=["region"], strategy="rare", min_exposure=None).fit(df)


def test_autogrouper_synthetic_labels_avoid_real_level_names() -> None:
    """A real level named like the synthetic namespace (group_0) must keep its
    own group; the synthetic label is renamed instead of colliding."""
    rng = np.random.default_rng(1)
    n = 300
    df = pd.DataFrame(
        {
            "feat": rng.choice(["A", "B", "group_0"], size=n),
            "exposure": np.ones(n),
            "target": rng.poisson(100, n).astype(float),
        }
    )
    grouper = AutoGrouper(
        cols=["feat"],
        strategy="similarity",
        max_groups=2,
        exposure_col="exposure",
        target_col="target",
    ).fit(df)
    mapping = grouper.mapping_["feat"]
    assert mapping["group_0"] == "group_0"  # real level keeps its name
    synthetic = {label for level, label in mapping.items() if level != "group_0"}
    assert len(synthetic) == 1
    assert next(iter(synthetic)) != "group_0"
    out = grouper.transform(df)
    assert out["feat"].nunique() == 2  # requested two groups stay two groups


# ---------------------------------------------------------------------------
# One-day exposure floor for min_exposure (M33)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cls", [AutoBinner, AutoGrouper])
def test_min_exposure_below_one_day_raises(cls) -> None:
    with pytest.raises(ValueError, match="1/366"):
        cls(min_exposure=1e-9, exposure_col="exposure").fit(_df())


@pytest.mark.parametrize(
    ("cls", "kwargs"),
    [(AutoBinner, {}), (AutoGrouper, {"strategy": "rare"})],
    ids=["binner", "grouper"],
)
def test_min_exposure_requires_a_real_exposure_column(cls, kwargs) -> None:
    """A floor without an exposure column previously fell back to row counts,
    silently changing units. min_exposure=None keeps the unfloored behaviour."""
    with pytest.raises(ValueError, match="min_exposure requires exposure_col"):
        cls(min_exposure=10.0, **kwargs).fit(_df())
    with pytest.raises(ValueError, match="configured column 'nope' not found"):
        cls(min_exposure=10.0, exposure_col="nope", **kwargs).fit(_df())
    cls(min_exposure=None, **kwargs).fit(_df())


@pytest.mark.parametrize("max_groups", [0, -1])
def test_autogrouper_rejects_max_groups_below_one(max_groups) -> None:
    """0 used to mean 'no limit' by truthiness and -1 crashed in the merge
    loop with `min() iterable argument is empty`; both must fail closed."""
    with pytest.raises(ValueError, match="max_groups must be at least 1"):
        AutoGrouper(max_groups=max_groups, exposure_col="exposure", target_col="claim_amount").fit(
            _df()
        )


@pytest.mark.parametrize("weighted", [False, True])
def test_autobinner_quantile_point_mass_at_min_has_no_empty_first_bin_and_observed_tariff_ref(
    weighted: bool,
) -> None:
    from azoic.tariff import extract_tariff

    values = np.r_[np.zeros(40), np.arange(1.0, 61.0)]
    df = pd.DataFrame({"x": values, "exposure": np.ones(len(values))})
    y = 1.0 + 0.05 * values
    binner = AutoBinner(
        cols=["x"],
        strategy="quantile",
        max_bins=5,
        exposure_col="exposure" if weighted else None,
    ).fit(df)
    edges = binner.mapping_["x"]
    assert np.all(edges > values.min())
    transformed = binner.transform(df)
    first_cat = transformed["x"].cat.categories[0]
    assert (transformed["x"] == first_cat).sum() > 0

    glm = RiskGLM(family="poisson", link="log", exposure_col="exposure").fit(transformed, y)
    tariff = extract_tariff(glm)
    ref = tariff["reference"]["x"]
    assert (transformed["x"] == ref).any()

    top_heavy = pd.DataFrame({"x": [0.0, 1.0, 1.0, 1.0], "exposure": np.ones(4)})
    top_binner = AutoBinner(
        cols=["x"],
        strategy="quantile",
        max_bins=2,
        exposure_col="exposure" if weighted else None,
    ).fit(top_heavy)
    np.testing.assert_array_equal(top_binner.mapping_["x"], [1.0])
    top_codes = top_binner.transform(top_heavy)["x"].cat.codes.tolist()
    assert top_codes == [0, 1, 1, 1]


@pytest.mark.parametrize("inf_val", [np.inf, -np.inf])
@pytest.mark.parametrize("as_dataframe", [True, False])
def test_autobinner_rejects_inf_in_fit_and_transform_and_roundtrips_mapping(
    inf_val: float, as_dataframe: bool
) -> None:
    clean_df = pd.DataFrame({"x": [0.0, 1.0, 2.0, np.nan]})
    dirty_df = pd.DataFrame({"x": [0.0, 1.0, inf_val, np.nan]})
    clean = clean_df if as_dataframe else clean_df.to_numpy()
    dirty = dirty_df if as_dataframe else dirty_df.to_numpy()

    with pytest.raises(ValueError, match="infinite"):
        AutoBinner(max_bins=2).fit(dirty)

    binner = AutoBinner(max_bins=2).fit(clean)
    expected = binner.transform(clean)
    binner.set_mapping(binner.mapping_)
    actual = binner.transform(clean)
    if as_dataframe:
        pd.testing.assert_frame_equal(actual, expected)
    else:
        np.testing.assert_array_equal(actual, expected)

    with pytest.raises(ValueError, match="infinite"):
        binner.transform(dirty)


def test_autobinner_default_cols_exclude_boolean_dtypes() -> None:
    df = pd.DataFrame(
        {
            "num": [1.0, 2.0, 3.0, 4.0],
            "flag_bool": [True, False, True, False],
            "flag_nullable": pd.Series([True, False, pd.NA, True], dtype="boolean"),
        }
    )
    binner = AutoBinner(max_bins=2).fit(df)
    assert binner.bin_cols_ == ["num"]
    assert list(binner.mapping_) == ["num"]
    out = binner.transform(df)
    pd.testing.assert_series_equal(out["flag_bool"], df["flag_bool"])
    pd.testing.assert_series_equal(out["flag_nullable"], df["flag_nullable"])


@pytest.mark.parametrize("cls", [AutoBinner, AutoGrouper])
def test_preprocessing_transform_tolerates_absent_special_columns(cls) -> None:
    df = _df(n=400)
    cols = ["driver_age", "vehicle_age"] if cls is AutoBinner else ["region", "vehicle_brand"]
    kwargs = {"strategy": "tree", "max_bins": 4} if cls is AutoBinner else {"max_groups": 3}
    transformer = cls(
        cols=cols,
        exposure_col="exposure",
        claim_count_col="claim_count",
        target_col="claim_amount",
        **kwargs,
    ).fit(df)

    full = transformer.transform(df)
    without_outcomes = transformer.transform(df.drop(columns=["claim_amount", "claim_count"]))
    features_only = transformer.transform(
        df.drop(columns=["exposure", "claim_amount", "claim_count"])
    )

    feature_cols = ["driver_age", "vehicle_age", "region", "vehicle_brand"]
    pd.testing.assert_frame_equal(without_outcomes[feature_cols], full[feature_cols])
    pd.testing.assert_frame_equal(features_only, full[feature_cols])

    with pytest.raises(ValueError, match="Transform predictors must match fit names and order"):
        transformer.transform(df[["vehicle_age", "driver_age", "region", "vehicle_brand"]])
    with pytest.raises(ValueError, match="Transform predictors must match fit names and order"):
        transformer.transform(df[["driver_age", "region", "vehicle_brand"]])


def test_autogrouper_merge_loop_matches_reference_and_1000_levels_under_one_second() -> None:
    import time

    rng = np.random.default_rng(42)
    n_rows = 2_000
    levels = np.array([f"lvl_{i:03d}" for i in range(120)])
    df = pd.DataFrame(
        {
            "cat": rng.choice(levels, size=n_rows),
            "exposure": rng.uniform(0.1, 2.0, size=n_rows),
            "claim_count": rng.poisson(0.2, size=n_rows).astype(float),
        }
    )
    df["claim_amount"] = df["claim_count"] * rng.gamma(2.0, 100.0, size=n_rows)

    grouper = AutoGrouper(
        cols=["cat"],
        strategy="similarity",
        max_groups=8,
        min_exposure=15.0,
        min_claims=3.0,
        exposure_col="exposure",
        claim_count_col="claim_count",
        target_col="claim_amount",
    ).fit(df)

    stats = grouper._level_stats(
        df["cat"],
        df["exposure"].to_numpy(),
        df["claim_count"].to_numpy(),
        df["claim_amount"].to_numpy(),
    ).sort_values("pp", kind="stable")
    groups = [[level] for level in stats.index]

    def total(group, column):
        return float(stats.loc[group, column].sum())

    def risk(group):
        exposure = total(group, "exp")
        return total(group, "tgt") / exposure if exposure > 0 else 0.0

    while len(groups) > 1:
        index = next(
            (
                i
                for i, group in enumerate(groups)
                if total(group, "exp") < 15.0 or total(group, "cc") < 3.0
            ),
            None,
        )
        if index is None:
            break
        if index == 0:
            merge_left = False
        elif index == len(groups) - 1:
            merge_left = True
        else:
            merge_left = abs(risk(groups[index]) - risk(groups[index - 1])) <= abs(
                risk(groups[index]) - risk(groups[index + 1])
            )
        if merge_left:
            groups[index - 1].extend(groups.pop(index))
        else:
            groups[index].extend(groups.pop(index + 1))

    while len(groups) > 8:
        differences = [abs(risk(groups[i]) - risk(groups[i + 1])) for i in range(len(groups) - 1)]
        index = min(range(len(differences)), key=differences.__getitem__)
        groups[index].extend(groups.pop(index + 1))

    expected = {}
    for i, group in enumerate(groups):
        label = group[0] if len(group) == 1 else f"group_{i}"
        for level in group:
            expected[level] = label
    assert grouper.mapping_["cat"] == expected

    big_levels = [f"k_{i:04d}" for i in range(1_000)]
    big_df = pd.DataFrame(
        {
            "cat": big_levels,
            "exposure": rng.uniform(0.5, 5.0, size=1_000),
            "claim_count": rng.poisson(1.0, size=1_000).astype(float),
            "claim_amount": rng.gamma(2.0, 50.0, size=1_000),
        }
    )
    start = time.perf_counter()
    big_grouper = AutoGrouper(
        cols=["cat"],
        strategy="similarity",
        max_groups=10,
        min_exposure=5.0,
        min_claims=2.0,
        exposure_col="exposure",
        claim_count_col="claim_count",
        target_col="claim_amount",
    ).fit(big_df)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
    assert len(set(big_grouper.mapping_["cat"].values())) == 10
