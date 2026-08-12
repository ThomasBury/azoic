"""Tests for riskforge.plots: lorenz / lift / calibration render headless to PNG.

The Agg backend is forced before importing riskforge.plots so pyplot never
tries to open a display (PRD M4 done-when: figures render headless to PNG).
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  (after use("Agg"))
import numpy as np  # noqa: E402
import pytest  # noqa: E402

from riskforge.metrics import calibration_table  # noqa: E402
from riskforge.plots import plot_calibration, plot_lift, plot_lorenz  # noqa: E402


def _portfolio_and_predictions(seed: int = 7, n: int = 4000):
    """Synthetic continuous y_true, y_pred, sample_weight for plot logic tests.

    The real synthetic_portfolio's pure premium has a huge zero mass (most
    policies have no claims), so ``pd.qcut(y_pred, 10, duplicates="drop")``
    would collapse to ~2 deciles and break the bar-count assertions -- these
    tests exercise *plot logic* (deciles, bar counts, savefile), not actuarial
    behaviour. Random exponential y with a noisy y_pred gives 10 distinct
    deciles and a positive Gini.
    """
    rng = np.random.default_rng(seed)
    y_true = rng.exponential(scale=1.0, size=n)
    y_pred = y_true * rng.uniform(0.5, 1.5, size=n)
    w = rng.uniform(0.5, 1.0, size=n)
    return y_true, y_pred, w


def test_plot_lorenz_writes_png_and_returns_axes(tmp_path) -> None:
    y_true, y_pred, w = _portfolio_and_predictions()
    out = tmp_path / "lorenz.png"
    ax = plot_lorenz(y_true, y_pred, w, path=out)
    assert isinstance(ax, plt.Axes)
    assert out.exists()
    assert out.stat().st_size > 500  # non-trivial PNG
    # Two lines drawn: the model curve + the random-diagonal reference.
    assert len(ax.get_lines()) == 2
    assert ax.get_xlim()[0] >= 0.0 and ax.get_xlim()[1] <= 1.0


def test_plot_lorenz_accepts_caller_axes() -> None:
    y_true, y_pred, w = _portfolio_and_predictions()
    fig, ax = plt.subplots()
    returned = plot_lorenz(y_true, y_pred, w, ax=ax)
    assert returned is ax


def test_plot_lift_writes_png(tmp_path) -> None:
    y_true, y_pred, w = _portfolio_and_predictions()
    tbl = calibration_table(y_true, y_pred, w, n_bins=10)
    out = tmp_path / "lift.png"
    ax = plot_lift(tbl, path=out)
    assert out.exists()
    assert out.stat().st_size > 500
    assert len(ax.patches) == 10  # one bar per decile segment
    heights = [float(p.get_height()) for p in ax.patches]
    assert any(h > 1.0 for h in heights) and any(h < 1.0 for h in heights)


def test_plot_lift_custom_baseline() -> None:
    y_true, y_pred, w = _portfolio_and_predictions()
    tbl = calibration_table(y_true, y_pred, w, n_bins=10)
    obs_pp = float(tbl["claim_amount"].sum() / tbl["exposure"].sum())
    ax_default = plot_lift(tbl)
    expected = (tbl["observed_pure_premium"] / obs_pp).to_numpy()
    heights = np.array([float(p.get_height()) for p in ax_default.patches])
    assert np.allclose(heights, expected, rtol=1e-9)
    ax_scaled = plot_lift(tbl, baseline=obs_pp / 2.0)
    heights_scaled = np.array([float(p.get_height()) for p in ax_scaled.patches])
    assert np.allclose(heights_scaled, expected * 2.0)


def test_plot_lift_zero_baseline_raises() -> None:
    y_true, y_pred, w = _portfolio_and_predictions()
    tbl = calibration_table(y_true, y_pred, w, n_bins=10)
    with pytest.raises(ValueError, match="`baseline`"):
        plot_lift(tbl, baseline=0.0)


def test_plot_calibration_writes_png(tmp_path) -> None:
    y_true, y_pred, w = _portfolio_and_predictions()
    tbl = calibration_table(y_true, y_pred, w, n_bins=10)
    out = tmp_path / "calibration.png"
    ax = plot_calibration(tbl, path=out)
    assert out.exists()
    assert out.stat().st_size > 500
    # One scatter collection + one diagonal reference line.
    assert len(ax.collections) == 1
    assert len(ax.get_lines()) == 1


def test_plots_round_trip_all_three_headless(tmp_path) -> None:
    y_true, y_pred, w = _portfolio_and_predictions()
    tbl = calibration_table(y_true, y_pred, w, n_bins=8)
    plot_lorenz(y_true, y_pred, w, path=tmp_path / "l.png")
    plot_lift(tbl, path=tmp_path / "lift.png")
    plot_calibration(tbl, path=tmp_path / "cal.png")
    for name in ("l.png", "lift.png", "cal.png"):
        out = tmp_path / name
        assert out.exists() and out.stat().st_size > 500
