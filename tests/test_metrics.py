"""Tests for riskforge.metrics: Gini, Lorenz, calibration table, deviances."""

from __future__ import annotations

import numpy as np

from riskforge.metrics import (
    calibration_table,
    gini,
    lorenz,
    mean_gamma_deviance,
    mean_poisson_deviance,
    mean_tweedie_deviance,
    op_ratio,
)
from tests.conftest import make_synthetic_portfolio


def _naive_gini(y_true, y_pred, w):
    """Slow reference, same actuarial convention as riskforge.metrics.gini."""
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


def test_lorenz_endpoints_and_monotonic() -> None:
    df = make_synthetic_portfolio(n=2000, seed=11)
    pp_true = df["claim_amount"] / df["exposure"]  # a naive "predicted" pp
    res = lorenz(df["claim_amount"].to_numpy(), pp_true.to_numpy(), df["exposure"].to_numpy())
    assert res.exposure_pct[0] == 0.0 and np.isclose(res.exposure_pct[-1], 1.0)
    assert res.claims_pct[0] == 0.0 and np.isclose(res.claims_pct[-1], 1.0)
    assert np.all(np.diff(res.exposure_pct) >= 0)
    assert np.all(np.diff(res.claims_pct) >= 0)
    assert res.gini > 0.0


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


def test_op_ratio_value() -> None:
    df = make_synthetic_portfolio(n=2000, seed=9)
    y_true = df["claim_amount"].to_numpy()
    y_pred = df["claim_amount"].to_numpy() / df["exposure"].to_numpy()
    w = df["exposure"].to_numpy()
    assert np.isclose(op_ratio(y_true, y_pred, w), 1.0)


def test_deviances_reexported() -> None:
    assert callable(mean_tweedie_deviance)
    assert callable(mean_poisson_deviance)
    assert callable(mean_gamma_deviance)
    y = np.array([1.0, 0.5, 2.0])
    p = np.array([1.1, 0.6, 1.8])
    assert mean_poisson_deviance(y, p) >= 0.0
