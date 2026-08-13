"""Actuarial diagnostics: exposure-weighted Gini, Lorenz, calibration table.

Pure-premium convention (see PRD.md section 5):
    y_true  = claim_amount (aggregate)
    y_pred  = predicted pure premium (rate per exposure unit)
    sample_weight = exposure

Deviances are re-exported from sklearn (never reimplemented) -- they already
accept `sample_weight`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import mean_gamma_deviance, mean_poisson_deviance, mean_tweedie_deviance

from riskforge.validation import make_strata

__all__ = [
    "gini",
    "lorenz",
    "Lorenz",
    "calibration_table",
    "op_ratio",
    "mean_tweedie_deviance",
    "mean_poisson_deviance",
    "mean_gamma_deviance",
]


def _as_arrays(y_true, y_pred, sample_weight=None):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    if sample_weight is None:
        sample_weight = np.ones_like(y_true)
    else:
        sample_weight = np.asarray(sample_weight, dtype=float)
    return y_true, y_pred, sample_weight


def _concentration_curve(y_true, y_pred, sample_weight):
    total_w = sample_weight.sum()
    total_o = y_true.sum()
    if total_w <= 0 or total_o <= 0:
        return np.array([0.0, 1.0]), np.array([0.0, 1.0])
    order = np.argsort(-y_pred, kind="stable")
    scores = y_pred[order]
    starts = np.r_[0, np.flatnonzero(scores[1:] != scores[:-1]) + 1]
    block_w = np.add.reduceat(sample_weight[order], starts)
    block_o = np.add.reduceat(y_true[order], starts)
    return (
        np.r_[0.0, np.cumsum(block_w) / total_w],
        np.r_[0.0, np.cumsum(block_o) / total_o],
    )


def gini(y_true, y_pred, sample_weight=None) -> float:
    """Exposure-weighted concentration Gini.

    Ranks policies by descending `y_pred` (high predicted risk first) and plots
    cumulative claim share against cumulative exposure share. Actuarial
    convention: a good model concentrates claims in the high-predicted-risk tail,
    so the curve rises above the diagonal. Equal prediction scores are aggregated
    before integration, making ties independent of row order. `gini = 2*area - 1`:
    ~[-1, 1], 0 = random, 1 = perfect, negative = inverse ranking.
    Returns 0 when total claims or total exposure is 0 (no signal).
    """
    y_true, y_pred, w = _as_arrays(y_true, y_pred, sample_weight)
    cum_w, cum_o = _concentration_curve(y_true, y_pred, w)
    area = np.trapezoid(cum_o, cum_w)
    return float(2.0 * area - 1.0)


@dataclass(frozen=True, slots=True)
class Lorenz:
    """Exposure-vs-claims concentration curve (sorted by descending y_pred)."""

    exposure_pct: np.ndarray
    claims_pct: np.ndarray
    gini: float


def lorenz(y_true, y_pred, sample_weight=None) -> Lorenz:
    """Return the concentration curve arrays plus the Gini.

    `exposure_pct` and `claims_pct` both start at 0.0 and end at 1.0, suitable
    for direct plotting. Sort direction matches `gini` (high y_pred first).
    """
    y_true, y_pred, w = _as_arrays(y_true, y_pred, sample_weight)
    cum_w, cum_o = _concentration_curve(y_true, y_pred, w)
    area = np.trapezoid(cum_o, cum_w)
    return Lorenz(exposure_pct=cum_w, claims_pct=cum_o, gini=float(2.0 * area - 1.0))


def op_ratio(y_true, y_pred, sample_weight=None) -> float:
    """Portfolio observed/predicted pure-premium ratio (1.0 = perfect level).

    observed  = sum(claim_amount) / sum(exposure)
    predicted = sum(pure_premium * exposure) / sum(exposure)
    """
    y_true, y_pred, w = _as_arrays(y_true, y_pred, sample_weight)
    total_w = w.sum()
    if total_w <= 0:
        return float("nan")
    observed_pp = y_true.sum() / total_w
    pred_pp = (y_pred * w).sum() / total_w
    if pred_pp <= 0:
        return float("nan")
    return float(observed_pp / pred_pp)


def calibration_table(
    y_true,
    y_pred,
    sample_weight=None,
    *,
    groups=None,
    n_bins: int = 10,
    claim_count=None,
) -> pd.DataFrame:
    """Per-segment observed vs predicted pure premium, exposure, and O/P ratio.

    `y_true` = claim_amount, `y_pred` = predicted pure premium, `sample_weight` =
    exposure. When `groups` is None, segments are deciles of predicted risk,
    exposure-weighted when `sample_weight` is supplied. Columns: group, exposure,
    claim_amount, predicted_claim_amount, observed_pure_premium,
    predicted_pure_premium, o_p_ratio; plus `claim_count` when provided.
    """
    weighted = sample_weight is not None
    y_true, y_pred, w = _as_arrays(y_true, y_pred, sample_weight)
    if groups is None:
        if weighted:
            groups = make_strata(y_pred, w, n_strata=n_bins)
        else:
            groups = pd.qcut(pd.Series(y_pred), n_bins, labels=False, duplicates="drop").to_numpy()
    df = pd.DataFrame(
        {"y_true": y_true, "y_pred": y_pred, "exposure": w, "group": np.asarray(groups)}
    )
    df["predicted_claim_amount"] = df["y_pred"] * df["exposure"]
    grouped = df.groupby("group", observed=True)
    out = grouped.agg(
        exposure=("exposure", "sum"),
        claim_amount=("y_true", "sum"),
        predicted_claim_amount=("predicted_claim_amount", "sum"),
    )
    if claim_count is not None:
        df["claim_count"] = np.asarray(claim_count, dtype=float)
        out["claim_count"] = grouped["claim_count"].sum()
    out["observed_pure_premium"] = out["claim_amount"] / out["exposure"]
    out["predicted_pure_premium"] = out["predicted_claim_amount"] / out["exposure"]
    out["o_p_ratio"] = out["observed_pure_premium"] / out["predicted_pure_premium"]
    return out.reset_index()
