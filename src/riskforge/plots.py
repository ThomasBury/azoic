"""Actuarial diagnostic plots: Lorenz, lift, calibration.

Three thin functions on top of ``riskforge.metrics`` diagnostics. Pass ``ax=``
to embed in your own figure, or ``path=`` to save a PNG. The module never
forces a backend -- tests / scripts set ``matplotlib.use("Agg")`` before
importing if headless rendering is needed (no display).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from riskforge.metrics import lorenz

__all__ = ["plot_lorenz", "plot_lift", "plot_calibration"]


def _ensure_ax(ax: plt.Axes | None = None, *, figsize=(5, 4)) -> plt.Axes:
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)
    return ax


def _maybe_save(ax: plt.Axes, path: str | Path | None) -> plt.Axes:
    if path is not None:
        ax.figure.savefig(str(path), dpi=120, bbox_inches="tight")
    return ax


def plot_lorenz(
    y_true,
    y_pred,
    sample_weight=None,
    *,
    ax: plt.Axes | None = None,
    path: str | Path | None = None,
    title: str = "Lorenz curve",
) -> plt.Axes:
    """Plot exposure-vs-claim concentration (high y_pred first) with the random diagonal."""
    ax = _ensure_ax(ax)
    res = lorenz(y_true, y_pred, sample_weight)
    ax.plot(res.exposure_pct, res.claims_pct, label=f"model (gini={res.gini:.3f})")
    ax.plot([0, 1], [0, 1], "--", color="0.5", label="random")
    ax.set_xlabel("Cumulative exposure share")
    ax.set_ylabel("Cumulative claim share")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title(title)
    ax.legend(loc="upper left")
    return _maybe_save(ax, path)


def plot_lift(
    table,
    *,
    baseline: Any = "observed",
    ax: plt.Axes | None = None,
    path: str | Path | None = None,
    title: str = "Lift by segment",
) -> plt.Axes:
    """Bar chart of observed pure premium per segment vs portfolio baseline.

    ``table`` is the output of ``riskforge.metrics.calibration_table`` (groups
    are predicted-risk deciles by default). Bars above ``1.0`` in the high-
    predicted-risk tail expose model ranking -- paired with the calibration
    plot for level adequacy. ``baseline`` can be ``"observed"`` (default;
    portfolio observed PP) or a scalar.
    """
    ax = _ensure_ax(ax)
    if baseline == "observed":
        base = float(table["claim_amount"].sum() / table["exposure"].sum())
    else:
        base = float(baseline)
    if base <= 0:
        raise ValueError(f"`baseline` resolves to {base}; must be > 0 to compute lift")
    lift = (table["observed_pure_premium"] / base).to_numpy()
    groups = [str(g) for g in np.asarray(table["group"])]
    x = np.arange(len(groups))
    ax.bar(x, lift)
    ax.axhline(1.0, color="0.5", linestyle="--", label="portfolio (1.0)")
    ax.set_xticks(x)
    ax.set_xticklabels(groups, rotation=45, ha="right")
    ax.set_xlabel("Segment (deciles of predicted risk by default)")
    ax.set_ylabel("Observed pure premium / portfolio")
    ax.set_title(title)
    ax.legend(loc="upper right")
    return _maybe_save(ax, path)


def plot_calibration(
    table,
    *,
    ax: plt.Axes | None = None,
    path: str | Path | None = None,
    title: str = "Calibration",
) -> plt.Axes:
    """Scatter observed vs predicted pure premium per segment with the y=x line.

    ``table`` is the output of ``riskforge.metrics.calibration_table``. The
    diagonal is the level-adequacy reference; dispersion around it is
    calibration error. Gini/ranking is read from the Lorenz plot, not this one.
    """
    ax = _ensure_ax(ax)
    obs = table["observed_pure_premium"].to_numpy(dtype=float)
    pred = table["predicted_pure_premium"].to_numpy(dtype=float)
    ax.scatter(pred, obs, s=30)
    lo = float(min(pred.min(), obs.min()))
    hi = float(max(pred.max(), obs.max()))
    pad = 0.05 * (hi - lo if hi > lo else 1.0)
    lims = [lo - pad, hi + pad]
    ax.plot(lims, lims, "--", color="0.5", label="perfect (y=x)")
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_xlabel("Predicted pure premium")
    ax.set_ylabel("Observed pure premium")
    ax.set_title(title)
    ax.legend(loc="upper left")
    return _maybe_save(ax, path)
