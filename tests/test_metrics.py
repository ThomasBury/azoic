"""Tests for azoic.metrics: Gini, Lorenz, calibration, one-way, double-lift, deviances."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from azoic.metrics import (
    calibration_table,
    double_lift_table,
    gini,
    lorenz,
    mean_gamma_deviance,
    mean_poisson_deviance,
    mean_tweedie_deviance,
    one_way_table,
    op_ratio,
    stability_table,
)
from tests.conftest import make_synthetic_portfolio


def _naive_gini(y_true, y_pred, w):
    """Slow reference, same actuarial convention as azoic.metrics.gini."""
    total_w = w.sum()
    total_o = y_true.sum()
    order = np.argsort(-y_pred, kind="stable")
    cum_w = np.cumsum(w[order]) / total_w
    cum_o = np.cumsum(y_true[order]) / total_o
    area = np.trapezoid(np.concatenate(([0.0], cum_o)), np.concatenate(([0.0], cum_w)))
    return 2.0 * area - 1.0


def test_gini_matches_reference_random() -> None:
    rng = np.random.default_rng(0)
    n = 500
    y_true = rng.poisson(0.5, size=n).astype(float)
    y_pred = rng.uniform(size=n)
    w = rng.uniform(0.5, 1.0, size=n)
    assert np.isclose(gini(y_true, y_pred, w), _naive_gini(y_true, y_pred, w), atol=1e-10)


def test_gini_self_ranking_is_positive() -> None:
    rng = np.random.default_rng(1)
    n = 2000
    y_true = rng.poisson(0.8, size=n).astype(float) + rng.uniform(size=n)
    w = rng.uniform(0.5, 1.0, size=n)
    g = gini(y_true, y_true, w)
    assert 0.0 < g < 1.0  # high but degenerate-portfolio < 1
    assert np.isclose(g, _naive_gini(y_true, y_true, w))


def test_gini_inverse_ranking_negates_self() -> None:
    rng = np.random.default_rng(2)
    n = 1000
    y_true = rng.poisson(0.7, size=n).astype(float) + rng.exponential(size=n)
    w = rng.uniform(0.3, 1.0, size=n)
    self_g = gini(y_true, y_true, w)
    inv_g = gini(y_true, -y_true, w)
    assert np.isclose(inv_g, -self_g, atol=1e-9)


def test_gini_random_near_zero() -> None:
    rng = np.random.default_rng(3)
    n = 50000
    y_true = rng.poisson(0.3, size=n).astype(float)
    y_pred = rng.uniform(size=n)
    w = rng.uniform(0.5, 1.0, size=n)
    assert abs(gini(y_true, y_pred, w)) < 0.05


def test_gini_zero_total_claims_or_exposure() -> None:
    assert gini(np.zeros(10), np.arange(10.0), np.ones(10)) == 0.0
    assert gini(np.arange(10.0), np.arange(10.0), np.zeros(10)) == 0.0


def test_gini_and_lorenz_are_invariant_within_prediction_ties() -> None:
    y_true = np.array([0.0, 8.0, 1.0, 5.0, 2.0])
    y_pred = np.array([3.0, 3.0, 2.0, 2.0, 1.0])
    exposure = np.array([1.0, 4.0, 2.0, 1.0, 3.0])
    perm = np.array([1, 0, 3, 2, 4])

    expected = lorenz(y_true, y_pred, exposure)
    actual = lorenz(y_true[perm], y_pred[perm], exposure[perm])

    assert gini(y_true, y_pred, exposure) == gini(y_true[perm], y_pred[perm], exposure[perm])
    np.testing.assert_allclose(actual.exposure_pct, expected.exposure_pct)
    np.testing.assert_allclose(actual.claims_pct, expected.claims_pct)
    assert len(actual.exposure_pct) == len(np.unique(y_pred)) + 1


def test_lorenz_endpoints_and_monotonic() -> None:
    df = make_synthetic_portfolio(n=2000, seed=11)
    pp_true = df["claim_amount"] / df["exposure"]  # a naive "predicted" pp
    res = lorenz(df["claim_amount"].to_numpy(), pp_true.to_numpy(), df["exposure"].to_numpy())
    assert res.exposure_pct[0] == 0.0 and np.isclose(res.exposure_pct[-1], 1.0)
    assert res.claims_pct[0] == 0.0 and np.isclose(res.claims_pct[-1], 1.0)
    assert np.all(np.diff(res.exposure_pct) >= 0)
    assert np.all(np.diff(res.claims_pct) >= 0)
    assert res.gini > 0.0
    assert np.all(res.claims_pct <= res.exposure_pct + 1e-12)
    assert np.isclose(res.gini, 1.0 - 2.0 * np.trapezoid(res.claims_pct, res.exposure_pct))


def test_calibration_table_totals_match_portfolio() -> None:
    df = make_synthetic_portfolio(n=3000, seed=7)
    y_true = df["claim_amount"].to_numpy()
    y_pred = df["claim_amount"].to_numpy() / df["exposure"].to_numpy()
    w = df["exposure"].to_numpy()
    tbl = calibration_table(y_true, y_pred, w, claim_count=df["claim_count"].to_numpy())
    assert np.isclose(tbl["exposure"].sum(), w.sum())
    assert np.isclose(tbl["claim_amount"].sum(), y_true.sum())
    assert np.isclose(tbl["predicted_claim_amount"].sum(), (y_pred * w).sum())
    assert np.allclose(tbl["o_p_ratio"], 1.0, atol=1e-9)
    assert "claim_count" in tbl.columns


def test_calibration_table_weighted_bins_balance_exposure() -> None:
    y_pred = np.arange(1.0, 101.0)
    exposure = np.linspace(1.0, 4.0, len(y_pred))
    tbl = calibration_table(y_pred * exposure, y_pred, exposure, n_bins=5)

    target = exposure.sum() / 5
    assert len(tbl) == 5
    assert np.all(np.abs(tbl["exposure"] - target) <= exposure.max())


def test_calibration_table_custom_groups() -> None:
    df = make_synthetic_portfolio(n=2000, seed=8)
    tbl = calibration_table(
        df["claim_amount"].to_numpy(),
        np.full(len(df), df["claim_amount"].sum() / df["exposure"].sum()),
        df["exposure"].to_numpy(),
        groups=df["region"].to_numpy(),
    )
    assert set(tbl["group"]) == {"urban", "suburban", "rural"}
    portfolio_pp = df["claim_amount"].sum() / df["exposure"].sum()
    assert np.allclose(tbl["predicted_pure_premium"], portfolio_pp)


def test_calibration_table_custom_groups_keep_missing_values() -> None:
    claims = np.array([1.0, 2.0, 3.0, 4.0])
    predictions = np.array([1.0, 1.0, 1.0, 1.0])
    exposure = np.array([1.0, 2.0, 3.0, 4.0])
    table = calibration_table(
        claims,
        predictions,
        exposure,
        groups=np.array(["review", None, "review", None], dtype=object),
    )

    assert pd.isna(table["group"]).sum() == 1
    assert np.isclose(table["exposure"].sum(), exposure.sum())
    assert np.isclose(table["claim_amount"].sum(), claims.sum())
    assert np.isclose(table["predicted_claim_amount"].sum(), np.dot(predictions, exposure))


def test_op_ratio_value() -> None:
    df = make_synthetic_portfolio(n=2000, seed=9)
    y_true = df["claim_amount"].to_numpy()
    y_pred = df["claim_amount"].to_numpy() / df["exposure"].to_numpy()
    w = df["exposure"].to_numpy()
    assert np.isclose(op_ratio(y_true, y_pred, w), 1.0)


def test_stability_table_matches_period_metrics_and_reconciles() -> None:
    df = make_synthetic_portfolio(n=2400, seed=18)
    y_true = df["claim_amount"].to_numpy()
    exposure = df["exposure"].to_numpy()
    y_pred = y_true / exposure + 0.25
    chronological = pd.period_range("2024-01", periods=4, freq="M")
    periods = np.resize(chronological.to_numpy()[[2, 0, 3, 1]], len(df))

    table = stability_table(y_true, y_pred, exposure, periods=periods)

    assert list(table.columns) == [
        "period",
        "exposure",
        "claim_amount",
        "predicted_claim_amount",
        "o_p_ratio",
        "gini",
        "deviance",
        "d2",
    ]
    assert table["period"].tolist() == chronological.tolist()
    assert np.isfinite(table.drop(columns="period").to_numpy(dtype=float)).all()

    for row in table.itertuples(index=False):
        mask = periods == row.period
        observed_rate = y_true[mask] / exposure[mask]
        expected_deviance = mean_tweedie_deviance(
            observed_rate,
            y_pred[mask],
            sample_weight=exposure[mask],
            power=1.5,
        )
        null_prediction = np.full(
            mask.sum(),
            y_true[mask].sum() / exposure[mask].sum(),
        )
        null_deviance = mean_tweedie_deviance(
            observed_rate,
            null_prediction,
            sample_weight=exposure[mask],
            power=1.5,
        )
        assert np.isclose(row.o_p_ratio, op_ratio(y_true[mask], y_pred[mask], exposure[mask]))
        assert np.isclose(row.gini, gini(y_true[mask], y_pred[mask], exposure[mask]))
        assert np.isclose(row.deviance, expected_deviance)
        assert np.isclose(row.d2, 1.0 - expected_deviance / null_deviance)

    assert np.isclose(table["exposure"].sum(), exposure.sum())
    assert np.isclose(table["claim_amount"].sum(), y_true.sum())
    assert np.isclose(table["predicted_claim_amount"].sum(), np.dot(y_pred, exposure))


def test_stability_table_rejects_missing_periods() -> None:
    with pytest.raises(ValueError, match="missing"):
        stability_table(
            [1.0, 2.0],
            [1.0, 1.0],
            [1.0, 1.0],
            periods=["2024-01", None],
        )


@pytest.mark.parametrize(
    ("y_true", "y_pred", "sample_weight", "periods", "message"),
    [
        ([], [], [], [], "non-empty"),
        ([[1.0]], [1.0], [1.0], ["2024-01"], "one-dimensional"),
        ([1.0], [1.0], [1.0], [["2024-01"]], "one-dimensional"),
        ([1.0, 2.0], [1.0], [1.0, 1.0], ["a", "b"], "same length"),
        ([1.0, 2.0], [1.0, 1.0], [1.0, 1.0], ["a"], "same length"),
        ([1.0, 2.0], [1.0, 1.0], [1.0, 1.0], [1.0, np.inf], "finite"),
        ([np.nan], [1.0], [1.0], ["a"], "non-negative finite"),
        ([-1.0], [1.0], [1.0], ["a"], "non-negative finite"),
        ([1.0], [np.inf], [1.0], ["a"], "positive finite"),
        ([1.0], [0.0], [1.0], ["a"], "positive finite"),
        ([1.0], [1.0], [np.nan], ["a"], "positive finite"),
        ([1.0], [1.0], [0.0], ["a"], "positive finite"),
    ],
)
def test_stability_table_rejects_invalid_inputs(
    y_true,
    y_pred,
    sample_weight,
    periods,
    message,
) -> None:
    with pytest.raises(ValueError, match=message):
        stability_table(y_true, y_pred, sample_weight, periods=periods)


def test_stability_table_rejects_sub_day_exposure() -> None:
    with pytest.raises(ValueError, match="1/366"):
        stability_table(
            [1.0, 2.0], [1.0, 2.0], [0.001, 1.0], periods=["a", "a"]
        )


def test_calibration_table_rejects_zero_exposure_segments() -> None:
    """A segment summing below one day of exposure produced inf/NaN silently
    (M33 F6); ranking curves keep zero weights legal, tables raise."""
    y_true = np.array([10.0, 20.0, 5.0, 7.0])
    y_pred = np.array([1.0, 2.0, 0.5, 0.7])
    w = np.array([1.0, 1.0, 0.0, 0.0])
    with pytest.raises(ValueError, match="1/366"):
        calibration_table(y_true, y_pred, w, groups=np.array(["a", "a", "b", "b"]))
    # exposure-weighted strata always absorb zero-weight rows into weighted
    # neighbours; only an all-zero portfolio produces a degenerate decile
    with pytest.raises(ValueError, match="1/366"):
        calibration_table(np.arange(10.0), np.arange(10.0), np.zeros(10), n_bins=10)


def test_one_way_table_rejects_zero_exposure_levels() -> None:
    X = pd.DataFrame({"f": ["a", "a", "b", "b"]})
    w = np.array([1.0, 1.0, 0.0, 0.0])
    with pytest.raises(ValueError, match="1/366"):
        one_way_table(X, "f", np.array([1.0, 2, 0, 0]), np.array([1.0, 2, 0.5, 0.7]), w)


def test_stability_table_zero_null_deviance_has_nan_d2() -> None:
    exposure = np.array([1.0, 2.0, 3.0])
    predictions = np.array([1.5, 2.0, 2.5])
    for claims in (np.zeros_like(exposure), 2.0 * exposure):
        table = stability_table(
            claims,
            predictions,
            exposure,
            periods=np.repeat("2024-01", len(exposure)),
        )

        assert np.isnan(table.loc[0, "d2"])
        assert np.isfinite(
            table.loc[0, ["o_p_ratio", "gini", "deviance"]].to_numpy(dtype=float)
        ).all()


def test_deviances_reexported() -> None:
    assert callable(mean_tweedie_deviance)
    assert callable(mean_poisson_deviance)
    assert callable(mean_gamma_deviance)
    y = np.array([1.0, 0.5, 2.0])
    p = np.array([1.1, 0.6, 1.8])
    assert mean_poisson_deviance(y, p) >= 0.0


def test_one_way_table_numeric_bins_matches_calibration_when_perfect() -> None:
    rng = np.random.default_rng(11)
    n = 3000
    X = pd.DataFrame({"driver_age": rng.integers(18, 90, size=n)})
    rate = rng.uniform(0.5, 2.0, size=n)
    w = rng.uniform(0.5, 1.0, size=n)
    y_true = rate * w  # observed aggregate claim_amount
    y_pred = rate  # perfect rate prediction
    tbl = one_way_table(X, "driver_age", y_true, y_pred, w, n_bins=10)
    assert len(tbl) >= 2 and len(tbl) <= 10
    assert np.isclose(tbl["exposure"].sum(), w.sum())
    assert np.isclose(tbl["claim_amount"].sum(), y_true.sum())
    assert np.isclose(tbl["predicted_claim_amount"].sum(), (y_pred * w).sum())
    assert np.allclose(tbl["o_p_ratio"], 1.0, atol=1e-9)
    assert set(tbl.columns) == {
        "level",
        "level_label",
        "level_center",
        "exposure",
        "claim_amount",
        "predicted_claim_amount",
        "observed_pure_premium",
        "predicted_pure_premium",
        "o_p_ratio",
    }
    assert tbl["level_center"].notna().all()
    assert (tbl["level_label"].str.startswith("[") & tbl["level_label"].str.endswith("]")).all()


@pytest.mark.parametrize("kind", ["calibration", "one_way", "double_lift"])
def test_diagnostic_quantiles_ignore_missing_exposure(kind) -> None:
    values = np.array([10, 20, 20, 30, 40, 50], dtype=float)
    exposure = np.array([1, 2, 3, 1, 2, 1], dtype=float)
    claims = values * exposure
    tables = []
    for missing in [False, True]:
        v = np.r_[values, np.nan] if missing else values
        w = np.r_[exposure, 1e9] if missing else exposure
        amounts = np.r_[claims, 10000] if missing else claims
        if kind == "calibration":
            if missing:
                # M31: a NaN prediction raises instead of silently dropping the row.
                with pytest.raises(ValueError, match="finite"):
                    calibration_table(amounts, v, w, n_bins=3)
                continue
            table = calibration_table(amounts, v, w, n_bins=3)
            table = table.loc[table["group"] >= 0]
        elif kind == "one_way":
            # A missing *feature* value keeps its own segment (documented); the
            # prediction vector stays finite, so totals must reconcile.
            table = one_way_table(
                pd.DataFrame({"value": v}), "value", amounts, np.full(len(v), 100), w, n_bins=3
            )
            np.testing.assert_allclose(
                table[["exposure", "claim_amount", "predicted_claim_amount"]].sum(),
                [w.sum(), amounts.sum(), 100 * w.sum()],
            )
            if missing:
                assert table.loc[table["level_label"] == "Missing", "claim_amount"].item() == 10000
            table = table.loc[table["level_center"].notna()]
        else:
            if missing:
                # M31: same fail-closed contract for the ratio strata.
                with pytest.raises(ValueError, match="finite"):
                    double_lift_table(amounts, v, np.ones(len(v)), w, n_bins=3)
                continue
            table = double_lift_table(amounts, v, np.ones(len(v)), w, n_bins=3)
        tables.append(table.reset_index(drop=True))
    if kind == "one_way":
        assert len(tables[0]) == 3
        pd.testing.assert_frame_equal(tables[1], tables[0])


@pytest.mark.parametrize("n_bins", [None, 10, 1])
@pytest.mark.parametrize("all_missing", [False, True])
@pytest.mark.parametrize("dtype", ["float64", "Float64"])
def test_one_way_table_retains_numeric_missing_segment(n_bins, all_missing, dtype) -> None:
    values = [np.nan, np.nan, np.nan] if all_missing else [20, 40, np.nan]
    X = pd.DataFrame({"age": pd.Series(values, dtype=dtype)})
    claims = np.array([100, 100, 10000])
    predictions = np.array([80, 60, 1500])
    exposure = np.array([1, 2, 5])
    table = one_way_table(X, "age", claims, predictions, exposure, n_bins=n_bins)
    np.testing.assert_allclose(
        table[["exposure", "claim_amount", "predicted_claim_amount"]].sum(),
        [8, 10200, 7700],
    )
    missing = table.loc[table["level_label"] == "Missing"]
    assert len(missing) == 1
    row = missing.iloc[0]
    assert np.isnan(row["level_center"])
    expected = [8, 10200, 7700] if all_missing else [5, 10000, 7500]
    np.testing.assert_allclose(
        row[["exposure", "claim_amount", "predicted_claim_amount"]].to_numpy(dtype=float), expected
    )
    assert row["observed_pure_premium"] == pytest.approx(expected[1] / expected[0])
    assert row["predicted_pure_premium"] == pytest.approx(expected[2] / expected[0])
    assert row["o_p_ratio"] == pytest.approx(expected[1] / expected[2])
    if all_missing:
        assert len(table) == 1


def test_one_way_table_categorical_passthrough() -> None:
    rng = np.random.default_rng(12)
    n = 2000
    X = pd.DataFrame({"region": rng.choice(["urban", "suburban", "rural"], size=n)})
    w = rng.uniform(0.5, 1.0, size=n)
    y_pred = np.full(n, 1.0)
    y_true = y_pred * w
    tbl = one_way_table(X, "region", y_true, y_pred, w)
    assert set(tbl["level"]) == {"urban", "suburban", "rural"}
    assert set(tbl["level_label"]) == {"urban", "suburban", "rural"}
    assert tbl["level_center"].isna().all()
    assert len(tbl) == 3
    assert np.allclose(tbl["o_p_ratio"], 1.0, atol=1e-9)


def test_one_way_table_missing_feature_raises() -> None:
    rng = np.random.default_rng(13)
    n = 200
    X = pd.DataFrame({"a": rng.integers(0, 100, size=n)})
    with np.testing.assert_raises(ValueError):
        one_way_table(X, "missing", rng.uniform(size=n), rng.uniform(size=n))


def test_double_lift_table_columns_and_shape() -> None:
    rng = np.random.default_rng(14)
    n = 4000
    y_true = rng.exponential(1.0, size=n)
    pred_a = y_true * rng.uniform(0.5, 1.5, size=n)
    pred_b = y_true * rng.uniform(0.8, 1.2, size=n)
    w = rng.uniform(0.5, 1.0, size=n)
    tbl = double_lift_table(
        y_true, pred_a, pred_b, w, n_bins=10, label_a="champion", label_b="benchmark"
    )
    assert 1 <= len(tbl) <= 10
    for col in (
        "group",
        "mean_ratio",
        "exposure",
        "claim_amount",
        "observed_pure_premium",
        "champion_pure_premium",
        "benchmark_pure_premium",
    ):
        assert col in tbl.columns
    assert np.isclose(tbl["exposure"].sum(), w.sum(), atol=1e-9)


def test_double_lift_table_ratio_monotone() -> None:
    """Deciles are ordered by the ratio, so mean_ratio is non-decreasing."""
    rng = np.random.default_rng(15)
    n = 4000
    y_true = rng.exponential(1.0, size=n)
    pred_a = rng.uniform(0.1, 5.0, size=n)
    pred_b = rng.uniform(0.5, 2.0, size=n)
    w = rng.uniform(0.5, 1.0, size=n)
    tbl = double_lift_table(y_true, pred_a, pred_b, w, n_bins=10)
    assert np.all(np.diff(tbl["mean_ratio"].to_numpy()) >= 0.0)


def test_double_lift_table_zero_prediction_floored() -> None:
    """Predictions floored for the ratio so deciles stay finite."""
    rng = np.random.default_rng(16)
    n = 2000
    y_true = rng.exponential(1.0, size=n)
    pred_a = rng.uniform(0.1, 2.0, size=n)
    pred_b = np.zeros(n)  # exact zeros must not crash the ratio
    w = rng.uniform(0.5, 1.0, size=n)
    tbl = double_lift_table(y_true, pred_a, pred_b, w, n_bins=5)
    assert len(tbl) >= 1
    assert np.isfinite(tbl["mean_ratio"]).all()
    assert np.isfinite(tbl["model A_pure_premium"]).all()
    assert np.allclose(tbl["model B_pure_premium"], 0.0)


def test_double_lift_table_shape_mismatch_raises() -> None:
    rng = np.random.default_rng(17)
    n = 100
    y_true = rng.exponential(1.0, size=n)
    pred_a = rng.uniform(size=n)
    pred_b = rng.uniform(size=n + 1)
    w = rng.uniform(size=n)
    with np.testing.assert_raises(ValueError):
        double_lift_table(y_true, pred_a, pred_b, w)


def test_double_lift_rising_observations_can_match_model_b() -> None:
    observed = np.repeat([10.0, 20.0, 30.0], 4)
    pred_a = np.repeat([1.0, 20.0, 90.0], 4)
    table = double_lift_table(observed, pred_a, observed, n_bins=3, label_a="A", label_b="B")
    np.testing.assert_allclose(table.mean_ratio, [0.1, 1.0, 3.0])
    np.testing.assert_allclose(table.observed_pure_premium, [10.0, 20.0, 30.0])
    np.testing.assert_allclose(table.B_pure_premium, table.observed_pure_premium)
    np.testing.assert_allclose(table.observed_pure_premium - table.A_pure_premium, [9, 0, -60])
    np.testing.assert_allclose(table.exposure, [4, 4, 4])


@pytest.mark.parametrize("multiplicative", [False, True])
def test_grouped_residual_additive_and_multiplicative_levels(multiplicative) -> None:
    prediction = np.array([10.0, 20.0, 30.0])
    rate = 2 * prediction if multiplicative else prediction + 5
    exposure = np.array([1.0, 2.0, 1.0])
    factor = op_ratio(rate * exposure, prediction, exposure)
    table = calibration_table(rate * exposure, prediction, exposure, groups=np.arange(3))
    residual = table.observed_pure_premium - table.predicted_pure_premium
    np.testing.assert_allclose(residual, prediction if multiplicative else 5)
    np.testing.assert_allclose(
        rate - factor * prediction, [0, 0, 0] if multiplicative else [2.5, 0, -2.5]
    )


def test_concentration_gini_differs_from_inequality_and_is_twice_signed_area() -> None:
    rate = np.array([1.0, 3.0])
    exposure = np.array([1.0, 2.0])
    claims = rate * exposure
    pairwise = np.sum(
        exposure[:, None] * exposure[None, :] * abs(rate[:, None] - rate[None, :])
    ) / (2 * exposure.sum() * claims.sum())
    curve = lorenz(claims, rate, exposure)
    np.testing.assert_allclose(curve.exposure_pct, [0, 1 / 3, 1])
    np.testing.assert_allclose(curve.claims_pct, [0, 1 / 7, 1])
    area = 1 / 42 + 8 / 21
    assert area == pytest.approx(17 / 42)
    assert pairwise == pytest.approx(4 / 21)
    assert curve.gini == pytest.approx(2 * (0.5 - area))
    assert gini(claims, rate, exposure) == pytest.approx(pairwise)
    assert gini(claims, -rate, exposure) == pytest.approx(-pairwise)
    assert gini(claims, 7 * rate, exposure) == pytest.approx(pairwise)


def test_one_way_ordered_intervals_keep_order_observed_groups_and_missing_totals() -> None:
    categories = ["(-inf, 2)", "[2, 10)", "[10, 20)", "[20, inf)"]
    X = pd.DataFrame(
        {
            "age": pd.Categorical(
                ["[10, 20)", "[2, 10)", None, "(-inf, 2)", "[2, 10)"],
                categories=categories,
                ordered=True,
            )
        }
    )
    exposure = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    claims = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    table = one_way_table(X, "age", claims, np.full(5, 10.0), exposure)
    assert table.level_label.tolist() == [*categories[:3], "nan"]
    assert len(table) == 4
    assert pd.isna(table.level.iloc[-1])
    np.testing.assert_allclose(table.exposure, [4, 7, 1, 3])
    np.testing.assert_allclose(table.claim_amount, [40, 70, 10, 30])
    assert table.exposure.sum() == exposure.sum()
    assert table.claim_amount.sum() == claims.sum()
    assert table.predicted_claim_amount.sum() == 10 * exposure.sum()


# ---------------------------------------------------------------------------
# Non-finite / invalid input validation (M31 -- fail-closed diagnostics)
# ---------------------------------------------------------------------------


def _diag_inputs():
    y_true = np.array([100.0, 0.0, 50.0, 25.0, 10.0])
    y_pred = np.array([1.0, 0.0, 2.0, 1.5, 0.8])  # exact zero stays legitimate
    w = np.array([1.0, 2.0, 1.0, 1.0, 0.5])
    return y_true, y_pred, w


def _call_diag(func, y_true, y_pred, w):
    if func is one_way_table:
        X = pd.DataFrame({"f": ["a"] * len(y_true)})
        return func(X, "f", y_true, y_pred, w, n_bins=None)
    if func is double_lift_table:
        return func(y_true, y_pred, np.full(len(y_true), 1.1), w)
    return func(y_true, y_pred, w)


@pytest.mark.parametrize(
    "func", [gini, lorenz, op_ratio, calibration_table, one_way_table, double_lift_table]
)
@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
@pytest.mark.parametrize("slot", ["y_true", "y_pred", "sample_weight"])
def test_diagnostics_reject_nonfinite_inputs(func, slot, bad) -> None:
    arrays = {"y_true": None, "y_pred": None, "sample_weight": None}
    y_true, y_pred, w = _diag_inputs()
    arrays.update({"y_true": y_true, "y_pred": y_pred, "sample_weight": w})
    arrays[slot] = arrays[slot].copy()
    arrays[slot][2] = bad
    with pytest.raises(ValueError, match="finite"):
        _call_diag(func, arrays["y_true"], arrays["y_pred"], arrays["sample_weight"])


@pytest.mark.parametrize(
    "func", [gini, lorenz, op_ratio, calibration_table, one_way_table, double_lift_table]
)
def test_diagnostics_reject_negative_claims_and_weights(func) -> None:
    y_true, y_pred, w = _diag_inputs()
    with pytest.raises(ValueError, match="non-negative finite claim amounts"):
        _call_diag(func, -y_true, y_pred, w)
    with pytest.raises(ValueError, match="finite non-negative exposures"):
        _call_diag(func, y_true, y_pred, -w)


@pytest.mark.parametrize(
    "func", [gini, lorenz, op_ratio, calibration_table, one_way_table, double_lift_table]
)
def test_diagnostics_reject_mismatched_or_multidimensional_inputs(func) -> None:
    y_true, y_pred, w = _diag_inputs()
    with pytest.raises(ValueError, match="same length"):
        _call_diag(func, y_true, y_pred[:-1], w)
    with pytest.raises(ValueError, match="one-dimensional"):
        _call_diag(func, y_true.reshape(-1, 1), y_pred, w)


def test_diagnostics_accept_exact_zero_predictions() -> None:
    y_true, y_pred, w = _diag_inputs()
    assert np.isfinite(gini(y_true, y_pred, w))
    table = calibration_table(y_true, y_pred, w, n_bins=2)
    assert np.isfinite(table["o_p_ratio"].fillna(1.0)).all()


def test_double_lift_rejects_nonfinite_pred_b() -> None:
    y_true, y_pred, w = _diag_inputs()
    pred_b = np.array([1.0, np.nan, 2.0, 1.0, 0.5])
    with pytest.raises(ValueError, match="pred_b must contain only finite predictions"):
        double_lift_table(y_true, y_pred, pred_b, w)


def test_double_lift_nan_prediction_raises_instead_of_dropping_claims() -> None:
    """Reported reproduction: a 3-row portfolio with 1,030 claims reported only
    30 -- the NaN-prediction row was silently dropped by the strata filter."""
    y_true = np.array([1000.0, 20.0, 10.0])
    pred_a = np.array([np.nan, 1.0, 2.0])
    pred_b = np.array([5.0, 1.0, 1.0])
    w = np.ones(3)
    with pytest.raises(ValueError, match="finite"):
        double_lift_table(y_true, pred_a, pred_b, w, n_bins=2)


def test_calibration_table_rejects_invalid_claim_count() -> None:
    y_true, y_pred, w = _diag_inputs()
    for bad_counts in ([1, 2, np.nan, 0, 1], [1, 2, -3, 0, 1]):
        with pytest.raises(ValueError, match="claim_count"):
            calibration_table(y_true, y_pred, w, claim_count=bad_counts)


def test_one_way_table_keeps_genuine_nan_string_distinct_from_missing() -> None:
    """A genuine "nan" string level must not merge with true missing values."""
    X = pd.DataFrame({"feat": pd.array(["nan", "a", None, "a"], dtype=object)})
    table = one_way_table(X, "feat", [1.0, 2.0, 3.0, 4.0], [1.0] * 4, [1.0] * 4, n_bins=None)
    assert len(table) == 3
    genuine = table.loc[table["level"] == "nan"]
    missing = table.loc[table["level"].isna()]
    assert genuine["claim_amount"].item() == 1.0
    assert missing["claim_amount"].item() == 3.0
    assert missing["level_label"].item() == "nan"
