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
@pytest.mark.parametrize("max_bins", [0, -1, 2.5, 2.0, True, None])
def test_autobinner_rejects_invalid_bin_counts(strategy, max_bins) -> None:
    with pytest.raises(ValueError, match="max_bins"):
        AutoBinner(strategy=strategy, max_bins=max_bins).fit(
            pd.DataFrame({"x": [0.0, 1.0, 2.0]}), [1.0, 2.0, 3.0]
        )


@pytest.mark.parametrize("edges", [[2, 1], [1, 1], [np.nan], [np.inf], [[1, 2]]])
def test_autobinner_invalid_mapping_preserves_state(edges) -> None:
    df = pd.DataFrame({"x": [0.0, 1.0, 2.0], "z": [1.0, 2.0, 3.0]})
    binner = AutoBinner(strategy="quantile", cols=["x", "z"]).fit(df)
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
    transformer.set_mapping({"x": values}, missing={"x": 0 if cls is AutoBinner else 10})
    out = transformer.transform(df)
    assert list(transformer.mapping_) == ["x"]
    pd.testing.assert_series_equal(out["z"], df["z"])
    assert transformer.missing_["x"] == (0 if cls is AutoBinner else 10)


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
    expected = [0, 0, 1, 1] if cls is AutoBinner else [actual[0]] * 2 + [actual[2]] * 2
    assert actual[0] != actual[2]
    assert list(actual) == expected


def _df(seed: int = 0, n: int = 4000) -> pd.DataFrame:
    return make_synthetic_portfolio(n=n, seed=seed)


# ---------------------------------------------------------------------------
# AutoBinner
# ---------------------------------------------------------------------------


def test_autobinner_quantile_bins_numeric_only() -> None:
    df = _df()
    binner = AutoBinner(strategy="quantile", cols=["driver_age", "vehicle_age"], max_bins=5).fit(df)
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
    binner = AutoBinner(
        strategy="quantile", cols=["driver_age"], max_bins=6, exposure_col="exposure"
    ).fit(df)
    # weighted edges present and sorted
    edges = binner.mapping_["driver_age"]
    assert np.all(np.diff(edges) > 0)


def test_autobinner_quantiles_ignore_missing_exposure() -> None:
    observed = pd.DataFrame({"value": [10, 20, 20, 30, 40, 50], "exposure": [1, 2, 3, 1, 2, 1]})
    extended = pd.concat(
        [observed, pd.DataFrame({"value": [np.nan], "exposure": [1e9]})], ignore_index=True
    )
    baseline = AutoBinner(
        strategy="quantile", cols=["value"], max_bins=3, exposure_col="exposure"
    ).fit(observed)
    binner = AutoBinner(
        strategy="quantile", cols=["value"], max_bins=3, exposure_col="exposure"
    ).fit(extended)
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
        strategy="quantile",
        cols=["driver_age"],
        max_bins=10,
        min_exposure=big_floor,
        exposure_col="exposure",
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
    binner = AutoBinner(strategy="quantile", cols=["driver_age"]).fit(df)
    binner.set_mapping(custom)
    assert np.allclose(binner.mapping_["driver_age"], custom["driver_age"])
    out = binner.transform(df)
    assert out["driver_age"].nunique() <= 4
    assert "(-inf, 25)" in out["driver_age"].cat.categories


@pytest.mark.parametrize(
    ("training", "edges", "labels"),
    [
        ([np.nan, np.nan], [], ["(-inf, inf)"]),
        ([0.0, 60.0], [30.0], ["(-inf, 30)", "[30, inf)"]),
        (
            [0.0, 30.0, 60.0, 90.0],
            [30.0, 60.0],
            ["(-inf, 30)", "[30, 60)", "[60, inf)"],
        ),
    ],
)
def test_autobinner_interval_boundaries_and_mapping_roundtrip(training, edges, labels) -> None:
    binner = AutoBinner(strategy="quantile", cols=["x"], max_bins=max(2, len(edges) + 1)).fit(
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


def test_autobinner_concise_labels_and_close_edges():
    labels = AutoBinner._labels(np.arange(4), np.array([31.66100000001, 45.32200000001]))
    assert labels.tolist() == ["(-inf, 31.661)", "[31.661, 45.322)", "[45.322, inf)", "Missing"]
    edges = np.array([1.0000001, 1.0000002, 1.0000003, 1.0000004])
    dtype = AutoBinner._category_dtype(edges)
    assert dtype.categories.is_unique
    assert "[1.0000001, 1.0000002)" in dtype.categories


def test_autobinner_reserves_ordered_interval_vocabulary() -> None:
    df = pd.DataFrame({"x": [0.0, 1.0, 2.0, 3.0]})
    binner = AutoBinner(strategy="quantile", cols=["x"], max_bins=2).fit(df)

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
    binner = AutoBinner(strategy="quantile", max_bins=4).fit(X)
    out = binner.transform(X)
    assert out.shape == X.shape
    assert pd.api.types.is_numeric_dtype(pd.Series(out[:, 0]))


def test_autobinner_handles_nan() -> None:
    df = _df()
    df.loc[df.index[:50], "driver_age"] = np.nan
    binner = AutoBinner(strategy="quantile", cols=["driver_age"], max_bins=5).fit(df)
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
        strategy="quantile",
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
    ("rates", "exposures", "claims", "max_groups", "min_exposure", "min_claims"),
    [
        ([100, 101, 10000], [10, 10, 10], [5, 5, 5], 2, None, None),
        ([0, 4, 5, 8.7], [1, 9, 1, 1], [5, 5, 5, 5], 2, None, None),
        ([0, 1, 2.2, 3.6], [10, 10, 10, 10], [5, 5, 5, 5], 2, None, None),
        ([100, 101, 102], [10, 10, 10], [5, 5, 5], 2, None, None),
        ([100, 10000, 100], [10, 10, 10], [5, 5, 5], 2, None, None),
        ([100, 1000, 1001], [10, 1, 10], [5, 5, 5], 3, 5, None),
        ([100, 101, 1000], [10, 1, 10], [5, 5, 5], 3, 5, None),
        ([100, 101, 102], [10, 1, 10], [5, 5, 5], 3, 5, None),
        ([100, 1000, 1001], [10, 10, 10], [5, 1, 5], 3, None, 3),
        ([100, 101, 1000], [1, 1, 1], [1, 1, 1], 3, 5, 5),
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
def test_autogrouper_nominal_similarity_respects_limits_and_floors(
    rate_target, rates, exposures, claims, max_groups, min_exposure, min_claims
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
    assert set(mapping) == set(levels)
    out = grouper.transform(df)
    assert out["segment"].nunique() <= max_groups
    for _, indices in out.groupby("segment", observed=True).groups.items():
        if out["segment"].nunique() > 1:
            assert df.loc[indices, "exposure"].sum() >= (min_exposure or 0)
            assert df.loc[indices, "claim_count"].sum() >= (min_claims or 0)
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
    grouper.set_mapping(custom, missing={"region": "urban"})
    out = grouper.transform(df)
    assert set(out["region"].unique()) == {"urban", "rural"}
    assert list(out["region"].cat.categories) == ["urban", "rural"]


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
    labels = [mapping[level] for level in levels]
    assert len(set(labels)) <= 2
    assert len(list(dict.fromkeys(labels))) == len(
        [v for i, v in enumerate(labels) if i == 0 or v != labels[i - 1]]
    )
    out_groups = grouper.transform(df).groupby("segment", observed=True).groups
    assert all(df.loc[indices, "exposure"].sum() >= 5 for indices in out_groups.values())
    out = grouper.transform(df)
    assert out["segment"].cat.ordered
    assert list(out["segment"].cat.categories) == list(dict.fromkeys(labels))


def test_autogrouper_nominal_similarity_vocabulary_is_frozen() -> None:
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

    pd.testing.assert_frame_equal(
        grouper.transform(df), pd.concat([grouper.transform(df.iloc[[i]]) for i in range(len(df))])
    )
    assert not grouper.category_dtypes_["segment"].ordered


def test_autogrouper_set_mapping_rebuilds_ordered_vocabulary() -> None:
    dtype = pd.CategoricalDtype(["A", "B", "C"], ordered=True)
    grouper = AutoGrouper(cols=["segment"]).fit(
        pd.DataFrame({"segment": pd.Series(["A", "B", "C"], dtype=dtype)}),
        [1.0, 2.0, 3.0],
    )

    grouper.set_mapping(
        {"segment": {"B": "second", "A": "first", "C": "second"}},
        missing={"segment": "first"},
    )

    fitted = grouper.category_dtypes_["segment"]
    assert fitted.ordered
    assert list(fitted.categories) == ["second", "first"]


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
    [(AutoBinner, {"strategy": "quantile"}), (AutoGrouper, {"strategy": "rare"})],
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
        AutoBinner(strategy="quantile", max_bins=2).fit(dirty)

    binner = AutoBinner(strategy="quantile", max_bins=2).fit(clean)
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
    binner = AutoBinner(strategy="quantile", max_bins=2).fit(df)
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


def test_autogrouper_native_tree_handles_1000_levels_under_one_second() -> None:
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

    out = grouper.transform(df)
    assert out["cat"].nunique() <= 8
    for indices in out.groupby("cat", observed=True).groups.values():
        assert df.loc[indices, "exposure"].sum() >= 15
        assert df.loc[indices, "claim_count"].sum() >= 3

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
    assert 1 <= len(set(big_grouper.mapping_["cat"].values())) <= 10


@pytest.mark.parametrize("cls", [AutoBinner, AutoGrouper])
@pytest.mark.parametrize("target", [[[1], [2], [3]], [[1, 2, 3]], [1, 2]])
def test_preprocessing_strict_target_shape(cls, target):
    with pytest.raises(ValueError, match="one-dimensional|inconsistent numbers"):
        cls(cols=["x"]).fit(pd.DataFrame({"x": [0, 1, 2]}), target)


@pytest.mark.parametrize("cls", [AutoBinner, AutoGrouper])
@pytest.mark.parametrize("control", ["min_exposure", "min_claims"])
@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf, -1, True, "bad"])
def test_preprocessing_finite_controls(cls, control, value):
    df = pd.DataFrame({"x": [0, 1, 2], "e": 1.0, "n": 1.0})
    with pytest.raises(ValueError, match=control):
        cls(cols=["x"], exposure_col="e", claim_count_col="n", **{control: value}).fit(
            df, [1, 2, 3]
        )


@pytest.mark.parametrize("max_groups", [None, True, 2.5, np.nan, np.inf])
def test_autogrouper_integer_limit(max_groups):
    with pytest.raises(ValueError, match="max_groups"):
        AutoGrouper(max_groups=max_groups).fit(pd.DataFrame({"x": ["A", "B"]}), [1, 2])


@pytest.mark.parametrize("monotonic", ["bad", 1, [], np.nan])
@pytest.mark.parametrize("values", [[np.nan, np.nan], [1, 1]])
def test_monotonic_option_validated_without_target_or_variation(monotonic, values):
    with pytest.raises(ValueError, match="monotonic"):
        AutoBinner(strategy="quantile", monotonic=monotonic).fit(pd.DataFrame({"x": values}))


@pytest.mark.parametrize("cls", [AutoBinner, AutoGrouper])
def test_feature_names_out_checked_against_fit(cls):
    transformer = cls(cols=["x"]).fit(pd.DataFrame({"x": [0, 1, 2]}), [1, 2, 3])
    assert transformer.get_feature_names_out(["x"]).tolist() == ["x"]
    with pytest.raises(ValueError, match="fitted feature names"):
        transformer.get_feature_names_out(["wrong"])


@pytest.mark.parametrize("cls", [AutoBinner, AutoGrouper])
@pytest.mark.parametrize("values", [[5.0] * 4, [np.nan] * 4])
def test_native_constant_and_all_missing_features(cls, values):
    X = pd.DataFrame({"x": values})
    transformer = cls(cols=["x"]).fit(X, [1, 2, 3, 4])
    out = transformer.transform(X)
    assert out["x"].nunique() == 1
    assert not out["x"].isna().any()
    assert len(out["x"].cat.categories) == 1
    pd.testing.assert_frame_equal(
        out, pd.concat([transformer.transform(X.iloc[[i]]) for i in range(4)])
    )


@pytest.mark.parametrize("cls", [AutoBinner, AutoGrouper])
@pytest.mark.parametrize("limit", [1, 4])
@pytest.mark.parametrize("floor", [2.0, 1e6])
def test_native_floors_include_missing_and_impossible_portfolios(cls, limit, floor):
    X = pd.DataFrame(
        {"x": [0, 1, 2, 3, 4, np.nan], "e": [1, 3, 1, 4, 2, 1], "n": [0, 1, 1, 3, 0, 1]}
    )
    params = {"max_bins": limit} if cls is AutoBinner else {"max_groups": limit}
    fitted = cls(
        cols=["x"],
        exposure_col="e",
        claim_count_col="n",
        min_exposure=floor,
        min_claims=floor,
        **params,
    ).fit(X, [0, 1, 8, 2, 30, 100])
    out = fitted.transform(X)
    assert out["x"].nunique() <= limit
    groups = out.groupby("x", observed=True).groups
    if floor > X["e"].sum() or limit == 1:
        assert len(groups) == 1
    elif len(groups) > 1:
        for indices in groups.values():
            assert X.loc[indices, "e"].sum() >= floor
            assert X.loc[indices, "n"].sum() >= floor


def test_native_numeric_thresholds_and_roundtrip_use_less_equal():
    X = pd.DataFrame({"x": [10.0, 20.0, 30.0, 40.0, np.nan]})
    fitted = AutoBinner(max_bins=3).fit(X, [1, 1, 10, 20, 20])
    assert fitted.strategy == "tree"
    edges = fitted.mapping_["x"]
    assert len(edges) >= 1
    probe = pd.DataFrame(
        {
            "x": [
                value
                for edge in edges
                for value in (np.nextafter(edge, -np.inf), edge, np.nextafter(edge, np.inf))
            ]
            + [np.nan]
        }
    )
    out = fitted.transform(probe)
    for i in range(len(edges)):
        assert out["x"].cat.codes.iloc[i * 3 : i * 3 + 3].tolist() == [i, i, i + 1]
    assert out["x"].cat.codes.iloc[-1] == fitted.missing_["x"]
    assert "Missing" not in out["x"].cat.categories
    fitted.set_mapping(fitted.mapping_)
    pd.testing.assert_frame_equal(fitted.transform(probe), out)


@pytest.mark.parametrize("cls", [AutoBinner, AutoGrouper])
def test_changed_native_mapping_requires_explicit_missing_transactionally(cls):
    X = pd.DataFrame({"x": [10, 20, 30, 40, np.nan]})
    fitted = cls(cols=["x"]).fit(X, [1, 1, 5, 5, 5])
    out = fitted.transform(X)
    mapping = (
        {"x": [25.0]}
        if cls is AutoBinner
        else {"x": {10: "low", 20: "low", 30: "high", 40: "high"}}
    )
    with pytest.raises(ValueError, match="explicit missing destination"):
        fitted.set_mapping(mapping)
    pd.testing.assert_frame_equal(out, fitted.transform(X))
    with pytest.raises(ValueError):
        fitted.set_mapping(mapping, missing={"x": 99 if cls is AutoBinner else None})
    pd.testing.assert_frame_equal(out, fitted.transform(X))
    fitted.set_mapping(mapping, missing={"x": 1 if cls is AutoBinner else "high"})
    result = fitted.transform(X)
    assert result["x"].cat.codes.tolist() == [0, 0, 1, 1, 1]
    fitted.set_mapping(fitted.mapping_)
    pd.testing.assert_frame_equal(result, fitted.transform(X))
    if cls is AutoBinner:
        assert fitted.transform(pd.DataFrame({"x": [25.0]}))["x"].cat.codes.tolist() == [1]
    else:
        with pytest.warns(UserWarning, match="unseen"):
            assert fitted.transform(pd.DataFrame({"x": ["new"]}))["x"].iloc[0] == "high"


@pytest.mark.parametrize("cls", [AutoBinner, AutoGrouper])
def test_in_place_mapping_edits_still_require_missing_destination(cls):
    fitted = cls(cols=["x"]).fit(pd.DataFrame({"x": [10, 20, 30, 40]}), [1, 1, 5, 5])
    if cls is AutoBinner:
        fitted.mapping_["x"] = np.array([21.0])
    else:
        fitted.mapping_["x"][10] = "new"
    with pytest.raises(ValueError, match="explicit missing destination"):
        fitted.set_mapping(fitted.mapping_)


@pytest.mark.parametrize("ordered", [False, True])
def test_native_categorical_missing_unseen_and_frozen_vocabulary(ordered):
    dtype = pd.CategoricalDtype(["A", "B", "C", "unused"], ordered=ordered)
    X = pd.DataFrame({"x": pd.Series(["A", "B", "C", None] * 30, dtype=dtype)})
    fitted = AutoGrouper(cols=["x"], max_groups=3).fit(X, [1, 1, 10, 10] * 30)
    out = fitted.transform(X)
    probe = pd.DataFrame({"x": [None, "unused", "new"]})
    with pytest.warns(UserWarning, match="unseen"):
        result = fitted.transform(probe)
    assert result["x"].tolist() == [fitted.missing_["x"]] * 3
    assert result["x"].dtype == out["x"].dtype
    assert result["x"].cat.ordered == ordered
    fitted.set_mapping(fitted.mapping_)
    pd.testing.assert_frame_equal(out, fitted.transform(X))


@pytest.mark.parametrize("ordered", [False, True])
def test_weighted_native_partitions_match_replicated_exposure(ordered):
    X = pd.DataFrame(
        {"x": pd.Categorical(list("ABCDE"), ordered=ordered), "e": [9, 22, 25, 23, 28]}
    )
    y = np.array([22.0, 33.0, 32.0, 5.0, 24.0])
    weighted = AutoGrouper(cols=["x"], max_groups=2, exposure_col="e").fit(X, y)
    indices = np.repeat(np.arange(len(X)), X["e"])
    repeated = X.iloc[indices].drop(columns="e").reset_index(drop=True)
    expanded = AutoGrouper(cols=["x"], max_groups=2).fit(repeated, y[indices])
    assert weighted.mapping_ == expanded.mapping_
    if not ordered:
        plain = (
            AutoGrouper(cols=["x"], max_groups=2).fit(X, y).transform(X)["x"].cat.codes.to_numpy()
        )
        codes = weighted.transform(X)["x"].cat.codes.to_numpy()
        assert not np.array_equal(codes[:, None] == codes, plain[:, None] == plain)
    if ordered:
        labels = [weighted.mapping_["x"][level] for level in X["x"].cat.categories]
        assert sum(a != b for a, b in zip(labels[:-1], labels[1:], strict=True)) <= 1


def test_weighted_numeric_tree_matches_replicated_exposure():
    X = pd.DataFrame({"x": [10.0, 20.0, 30.0, 40.0], "e": [1, 9, 1, 1]})
    y = np.array([0.0, 4.0, 5.0, 8.7])
    weighted = AutoBinner(cols=["x"], max_bins=2, exposure_col="e").fit(X, y)
    indices = np.repeat(np.arange(len(X)), X["e"])
    expanded = AutoBinner(max_bins=2).fit(X.iloc[indices][["x"]], y[indices])
    unweighted = AutoBinner(max_bins=2).fit(X[["x"]], y)
    np.testing.assert_array_equal(weighted.mapping_["x"], expanded.mapping_["x"])
    assert not np.array_equal(weighted.mapping_["x"], unweighted.mapping_["x"])


@pytest.mark.parametrize("direction", ["increasing", "decreasing"])
def test_native_monotonic_means_and_floors_include_missing(direction):
    X = pd.DataFrame(
        {
            "x": np.r_[np.repeat(np.arange(8), 10), [np.nan] * 10],
            "e": np.tile([1.0, 3.0], 45),
            "n": 1.0,
        }
    )
    y = np.repeat([1.0, 8.0, 3.0, 6.0, 2.0, 9.0, 5.0, 10.0, 20.0], 10)
    fitted = AutoBinner(
        cols=["x"],
        max_bins=8,
        monotonic=direction,
        exposure_col="e",
        claim_count_col="n",
        min_exposure=10,
        min_claims=5,
    ).fit(X, y)
    out = fitted.transform(X)
    means = []
    for indices in out.groupby("x", observed=True).groups.values():
        assert X.loc[indices, "e"].sum() >= 10
        assert X.loc[indices, "n"].sum() >= 5
        means.append(np.average(y[indices], weights=X.loc[indices, "e"]))
    assert (
        np.all(np.diff(means) >= -1e-10)
        if direction == "increasing"
        else np.all(np.diff(means) <= 1e-10)
    )


def test_native_pipeline_serialization_and_tariff_agreement(tmp_path):
    import joblib

    from azoic.tariff import apply_tariff, extract_tariff

    X = pd.DataFrame(
        {"x": [10.0, 20.0, 30.0, 40.0, np.nan] * 30, "c": ["A", "A", "B", "C", None] * 30, "e": 1.0}
    )
    y = np.tile([1.0, 2.0, 5.0, 10.0, 15.0], 30)
    pipeline = Pipeline(
        [
            ("binner", AutoBinner(cols=["x"], max_bins=3, exposure_col="e")),
            ("grouper", AutoGrouper(cols=["c"], max_groups=2, exposure_col="e")),
            ("model", RiskGLM(family="poisson", link="log", exposure_col="e")),
        ]
    ).fit(X, y)
    transformed = pipeline[:-1].transform(X)
    np.testing.assert_allclose(
        pipeline.predict(X), apply_tariff(extract_tariff(pipeline[-1]), transformed)
    )
    path = tmp_path / "pipeline.joblib"
    joblib.dump(pipeline, path)
    loaded = joblib.load(path)
    np.testing.assert_array_equal(pipeline.predict(X), loaded.predict(X))
    pd.testing.assert_frame_equal(transformed, loaded[:-1].transform(X))


def test_nominal_native_splits_pool_nonadjacent_labels():
    X = pd.DataFrame({"x": list("ABCD") * 30})
    fitted = AutoGrouper(max_groups=2).fit(X, [1, 10, 1, 10] * 30)
    mapping = fitted.mapping_["x"]
    assert mapping["A"] == mapping["C"] != mapping["B"] == mapping["D"]


@pytest.mark.parametrize("cls", [AutoBinner, AutoGrouper])
def test_native_leaf_lookup_uses_leaf_ids_and_preserves_typed_categories(cls):
    values = [0.0, 1.0, 2.0, 3.0, np.nan] if cls is AutoBinner else [1, "A", ("B", 2), "C", None]
    frame = pd.DataFrame({"x": values * 40})
    targets = [1, 50, 10, 100, 3] if cls is AutoBinner else [100, 1, 50, 1, 3]
    fitted = cls(cols=["x"]).fit(frame, targets * 40)
    if cls is AutoBinner:
        probes = [np.nan, -1.0, 5.0]
        for edge in fitted.mapping_["x"]:
            probes.extend([np.nextafter(edge, -np.inf), edge, np.nextafter(edge, np.inf)])
        probe = pd.DataFrame({"x": probes})
        encoded = probe.x.to_numpy()
    else:
        assert 1 in fitted.category_dtypes_["x"].categories
        assert ("B", 2) in fitted.category_dtypes_["x"].categories
        probe = pd.DataFrame({"x": values + ["unseen"]})
        encoded = fitted._encoded(probe.x, fitted.levels_["x"])
    leaves = fitted.trees_["x"].predict(encoded.reshape(-1, 1), pred_leaf=True, num_threads=1)
    groups = fitted.leaf_groups_["x"]
    expected = [groups[int(leaf)] for leaf in np.asarray(leaves).ravel()]
    if cls is AutoBinner:
        expected = [fitted.category_dtypes_["x"].categories[code] for code in expected]
    fitted.leaf_groups_["x"] = dict(reversed(list(groups.items())))
    if cls is AutoGrouper:
        with pytest.warns(UserWarning, match="unseen"):
            actual = fitted.transform(probe)
    else:
        actual = fitted.transform(probe)
    assert actual.x.tolist() == expected
    assert actual.x.dtype == fitted.category_dtypes_["x"]


def test_claim_floor_prunes_siblings_without_reweighting_or_collapsing_everything():
    values = np.repeat(np.arange(8, dtype=float), 20)
    X = pd.DataFrame({"x": values, "e": 1.0, "n": np.where(values == 1, 0.0, 1.0)})
    y = np.repeat([1.0, 2.0, 4.0, 5.0, 10.0, 11.0, 20.0, 21.0], 20)
    params = {
        "cols": ["x"],
        "max_bins": 8,
        "exposure_col": "e",
        "claim_count_col": "n",
        "min_exposure": 20,
    }
    unrestricted = AutoBinner(**params).fit(X, y)
    fitted = AutoBinner(min_claims=15, **params).fit(X, y)
    out = fitted.transform(X)
    assert 1 < out["x"].nunique() < unrestricted.transform(X)["x"].nunique()
    for indices in out.groupby("x", observed=True).groups.values():
        assert X.loc[indices, "e"].sum() >= 20
        assert X.loc[indices, "n"].sum() >= 15
    changed_counts = X.assign(n=100.0)
    other = AutoBinner(**params).fit(changed_counts, y)
    np.testing.assert_array_equal(unrestricted.mapping_["x"], other.mapping_["x"])


@pytest.mark.parametrize("cls", [AutoBinner, AutoGrouper])
def test_native_transform_preserves_index_columns_and_passthrough(cls):
    X = pd.DataFrame(
        {"x": [10.0, 20.0, 30.0, 40.0], "passthrough": ["a", "b", "c", "d"]},
        index=pd.Index([10, 2, 7, 1], name="policy"),
    )
    fitted = cls(cols=["x"]).fit(X, [1, 1, 10, 10])
    out = fitted.transform(X)
    pd.testing.assert_index_equal(out.index, X.index)
    pd.testing.assert_index_equal(out.columns, X.columns)
    pd.testing.assert_series_equal(out["passthrough"], X["passthrough"])


def test_default_tree_requires_outcomes_and_quantile_does_not():
    X = pd.DataFrame({"x": [1.0, 2.0, 3.0]})
    with pytest.raises(ValueError, match="tree binning requires a target"):
        AutoBinner().fit(X)
    AutoBinner(strategy="quantile").fit(X)


def test_manual_missing_destination_takes_precedence_over_null_mapping_keys():
    X = pd.DataFrame({"x": ["A", "B", None]})
    fitted = AutoGrouper(cols=["x"]).fit(X, [1, 10, 10])
    fitted.set_mapping(
        {"x": {"A": "low", "B": "high", np.nan: "incidental"}},
        missing={"x": "Missing"},
    )
    assert fitted.transform(X)["x"].tolist() == ["low", "high", "Missing"]
    with pytest.warns(UserWarning, match="unseen"):
        out = fitted.transform(pd.DataFrame({"x": ["new"]}))
    assert out["x"].tolist() == ["Missing"]
    assert out["x"].cat.categories.tolist() == ["low", "high", "incidental", "Missing"]


def test_rare_grouping_preserves_declared_order_despite_encounter_order():
    X = pd.DataFrame(
        {"x": pd.Categorical(["A", "B", "C"], categories=["C", "B", "A"], ordered=True)}
    )
    fitted = AutoGrouper(strategy="rare").fit(X)
    assert fitted.transform(X)["x"].cat.categories.tolist() == ["C", "B", "A", "Other"]
    assert fitted.transform(X)["x"].cat.ordered
