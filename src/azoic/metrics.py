"""Actuarial diagnostics: ranking, calibration, stability, one-way, and double-lift.

Pure-premium convention (see PRD.md section 5):
    y_true  = claim_amount (aggregate)
    y_pred  = predicted pure premium (rate per exposure unit)
    sample_weight = exposure

Deviances are re-exported from sklearn (never reimplemented) -- they already
accept `sample_weight`.

Concentration curves order policies by ascending predicted rate. Gini is twice
the signed area from the curve to the diagonal: positive when claims tend to
concentrate at higher predictions, negative for the reverse. Tied-score blocks
are integrated, equivalently the Frees-Meyers-Cummings midrank formula. This is
a prediction-ordered measure. Observed-rate ordering recovers the corresponding
exposure-weighted pairwise inequality Gini.
"""

from __future__ import annotations

from collections import namedtuple

import numpy as np
import pandas as pd
from sklearn.metrics import (
    auc,
    mean_gamma_deviance,
    mean_poisson_deviance,
    mean_tweedie_deviance,
)

from azoic.validation import make_strata

__all__ = [
    "gini",
    "lorenz",
    "Lorenz",
    "calibration_table",
    "stability_table",
    "one_way_table",
    "double_lift_table",
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
    """Low-to-high (safest-to-riskiest) actuary concentration curve.

    Policies are ordered by ascending ``y_pred``; tied scores are aggregated
    into a single block before integration so the curve is permutation
    invariant. The curve starts at (0, 0) and ends at (1, 1); it can cross
    the diagonal even when its overall concentration Gini is positive.
    """
    total_w = sample_weight.sum()
    total_o = y_true.sum()
    if total_w <= 0 or total_o <= 0:
        return np.array([0.0, 1.0]), np.array([0.0, 1.0])
    order = np.argsort(y_pred, kind="stable")
    scores = y_pred[order]
    starts = np.r_[0, np.flatnonzero(scores[1:] != scores[:-1]) + 1]
    block_w = np.add.reduceat(sample_weight[order], starts)
    block_o = np.add.reduceat(y_true[order], starts)
    return (
        np.r_[0.0, np.cumsum(block_w) / total_w],
        np.r_[0.0, np.cumsum(block_o) / total_o],
    )


def gini(y_true, y_pred, sample_weight=None) -> float:
    """Exposure-weighted concentration Gini (actuarial low-to-high convention).

    ``y_true`` is aggregate claim amount, ``y_pred`` is predicted rate, and
    ``sample_weight`` is exposure (unit exposure when omitted). Order by
    ascending prediction and integrate cumulative claim share ``C(u)`` against
    cumulative exposure share ``u``: ``G = 1 - 2 * integral(C(u), u=0..1)``.
    This is twice the signed area from the curve to the diagonal, within
    [-1, 1] for non-negative claims and positive exposure. Negative values
    indicate claims concentrated toward lower predictions; zero need not
    imply random predictions. Observed-rate ordering gives a hindsight upper
    bound, generally below one, equal to exposure-weighted inequality Gini.

    Pairwise absolute-difference inequality Gini measures observed-rate
    dispersion independently of predictions. This implementation instead
    integrates tied-score blocks, equivalently the Frees-Meyers-Cummings
    midrank formula. Ties are independent of row order; positive scaling
    preserves Gini. Returns 0 when total claims or total exposure is 0.
    """
    y_true, y_pred, w = _as_arrays(y_true, y_pred, sample_weight)
    cum_w, cum_o = _concentration_curve(y_true, y_pred, w)
    return float(1.0 - 2.0 * auc(cum_w, cum_o))


Lorenz = namedtuple("Lorenz", ["exposure_pct", "claims_pct", "gini"])
"""Exposure-vs-claims concentration curve (actuarial ascending y_pred)."""


def lorenz(y_true, y_pred, sample_weight=None) -> Lorenz:
    """Return the ascending concentration curve plus the Gini.

    ``exposure_pct`` and ``claims_pct`` both start at 0.0 and end at 1.0,
    suitable for direct plotting. Policies are ordered by predicted rate,
    with equal scores aggregated before integration. The curve may cross the
    diagonal; Gini is twice its signed area to that diagonal. A lower curve
    dominates another only when it is nowhere above it.
    """
    y_true, y_pred, w = _as_arrays(y_true, y_pred, sample_weight)
    cum_w, cum_o = _concentration_curve(y_true, y_pred, w)
    return Lorenz(
        exposure_pct=cum_w,
        claims_pct=cum_o,
        gini=float(1.0 - 2.0 * auc(cum_w, cum_o)),
    )


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


def stability_table(y_true, y_pred, sample_weight, *, periods) -> pd.DataFrame:
    """Return exposure-weighted diagnostics for each naturally sorted period.

    ``y_true`` is aggregate claim amount, ``y_pred`` is predicted pure premium,
    and ``sample_weight`` is exposure. The fixed-power Tweedie deviance and
    period-relative :math:`D^2` use ``power=1.5``. ``D^2`` is ``NaN`` when the
    period's exposure-weighted observed-mean prediction has zero deviance.

    All inputs must be non-empty, one-dimensional, equal-length arrays without
    missing periods. Claim amounts must be non-negative and finite; predictions
    and exposures must be positive and finite.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    sample_weight = np.asarray(sample_weight, dtype=float)
    periods = np.asarray(periods)

    if any(values.ndim != 1 for values in (y_true, y_pred, sample_weight, periods)):
        raise ValueError("stability_table inputs must be one-dimensional")
    if len(y_true) == 0:
        raise ValueError("stability_table inputs must be non-empty")
    if len({len(y_true), len(y_pred), len(sample_weight), len(periods)}) != 1:
        raise ValueError("stability_table inputs must have the same length")
    if pd.isna(periods).any():
        raise ValueError("periods must not contain missing values")
    if pd.api.types.is_numeric_dtype(periods) and not np.isfinite(periods).all():
        raise ValueError("numeric periods must contain only finite values")
    if not np.isfinite(y_true).all() or np.any(y_true < 0):
        raise ValueError("y_true must contain only non-negative finite claim amounts")
    if not np.isfinite(y_pred).all() or np.any(y_pred <= 0):
        raise ValueError("y_pred must contain only positive finite predictions")
    if not np.isfinite(sample_weight).all() or np.any(sample_weight <= 0):
        raise ValueError("sample_weight must contain only positive finite exposures")

    frame = pd.DataFrame(
        {
            "period": periods,
            "claim_amount": y_true,
            "prediction": y_pred,
            "exposure": sample_weight,
        }
    )
    rows = []
    for period, group in frame.groupby("period", observed=True, sort=True):
        claims = group["claim_amount"].to_numpy()
        predictions = group["prediction"].to_numpy()
        exposure = group["exposure"].to_numpy()
        observed_rate = claims / exposure
        exposure_total = float(exposure.sum())
        claim_total = float(claims.sum())
        predicted_total = float(np.dot(predictions, exposure))
        deviance = float(
            mean_tweedie_deviance(
                observed_rate,
                predictions,
                sample_weight=exposure,
                power=1.5,
            )
        )
        null_deviance = 0.0
        if claim_total > 0:
            null_prediction = np.full_like(predictions, claim_total / exposure_total)
            null_deviance = float(
                mean_tweedie_deviance(
                    observed_rate,
                    null_prediction,
                    sample_weight=exposure,
                    power=1.5,
                )
            )
        rows.append(
            {
                "period": period,
                "exposure": exposure_total,
                "claim_amount": claim_total,
                "predicted_claim_amount": predicted_total,
                "o_p_ratio": op_ratio(claims, predictions, exposure),
                "gini": gini(claims, predictions, exposure),
                "deviance": deviance,
                "d2": 1.0 - deviance / null_deviance if null_deviance > 0 else float("nan"),
            }
        )

    out = pd.DataFrame.from_records(
        rows,
        columns=[
            "period",
            "exposure",
            "claim_amount",
            "predicted_claim_amount",
            "o_p_ratio",
            "gini",
            "deviance",
            "d2",
        ],
    )
    totals = out[["exposure", "claim_amount", "predicted_claim_amount"]].sum().to_numpy()
    expected = np.array([sample_weight.sum(), y_true.sum(), np.dot(y_pred, sample_weight)])
    if not np.allclose(totals, expected):
        raise RuntimeError("period totals do not reconcile with the complete input")
    return out


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
    exposure-weighted when `sample_weight` is supplied. Otherwise `groups` is an
    array-like of one segment label per row; NaN labels form their own segment
    (``dropna=False``). Columns: group, exposure, claim_amount,
    predicted_claim_amount, observed_pure_premium, predicted_pure_premium,
    o_p_ratio; plus `claim_count` when provided.
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
    grouped = df.groupby("group", observed=True, dropna=False)
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


def one_way_table(
    X: pd.DataFrame,
    feature: str,
    y_true,
    y_pred,
    sample_weight=None,
    *,
    n_bins: int | None = 10,
) -> pd.DataFrame:
    """Per-level observed vs predicted pure premium for one feature.

    Buckets rows by ``feature``. Categorical / low-cardinality features are
    kept at their actual level (grouped levels from ``AutoGrouper`` are
    preserved as-is, including declared ordered-category order). Numeric features
    with ``n_bins=None`` get one level
    per unique raw value (natural-value one-way on test rows: driver age
    has as many points as distinct values); an integer ``n_bins`` exposure-
    weight quantiles numeric features into ``n_bins`` bins for near-
    continuous features like density.

    ``y_true`` = claim_amount, ``y_pred`` = predicted pure premium (rate),
    ``sample_weight`` = exposure. Output columns:

    level, level_label, level_center, exposure, claim_amount,
    predicted_claim_amount, observed_pure_premium, predicted_pure_premium,
    o_p_ratio.

    ``level`` is the grouping key (integer code for numeric binned, raw value
    for numeric unique-value mode and categorical). ``level_label`` is a
    human-readable label (bin interval ``[a, b]`` for quantiled numeric, the
    actual level otherwise). ``level_center`` is the exposure-weighted mean
    of the raw feature within the bin (quantiled numeric only); the raw
    value itself in unique-value mode; ``NaN`` for categorical or missing
    values. Numeric missing rows retain their totals as ``Missing`` with
    an undefined centre, and their exposure does not affect bin boundaries.
    """
    if feature not in X.columns:
        raise ValueError(f"feature {feature!r} not in X.columns")
    y_true, y_pred, w = _as_arrays(y_true, y_pred, sample_weight)
    values = X[feature]
    is_numeric = pd.api.types.is_numeric_dtype(values)
    if is_numeric and n_bins is not None and values.nunique(dropna=True) > n_bins:
        raw = values.to_numpy(dtype=float)
        codes = make_strata(raw, w, n_strata=n_bins)
        valid = codes >= 0
        labels = _format_numeric_labels(raw, codes)
        centers = np.full(len(codes), np.nan, dtype=float)
        valid_codes = np.unique(codes[valid])
        for code in valid_codes:
            mask = codes == code
            total_w = w[mask].sum()
            centers[codes == code] = (
                np.average(raw[mask], weights=w[mask]) if total_w > 0 else np.nan
            )
        levels = codes
    elif is_numeric:
        raw = values.to_numpy(dtype=float)
        levels = raw
        labels = np.array(["Missing" if np.isnan(v) else f"{v:g}" for v in raw], dtype=object)
        centers = raw
    else:
        raw = values.astype(object).to_numpy()
        levels = np.where(pd.isna(raw), "nan", raw).astype(object)
        labels = np.array([str(v) for v in levels.tolist()], dtype=object)
        centers = np.full(len(raw), np.nan, dtype=float)
    df = pd.DataFrame(
        {
            "y_true": y_true,
            "y_pred": y_pred,
            "exposure": w,
            "level": levels,
            "level_label": labels,
            "level_center": centers,
        }
    )
    if isinstance(values.dtype, pd.CategoricalDtype) and values.dtype.ordered:
        df["level"] = pd.Categorical(values, dtype=values.dtype)
    df["predicted_claim_amount"] = df["y_pred"] * df["exposure"]
    grouped = df.groupby("level", observed=True, sort=True, dropna=False)
    out = grouped.agg(
        level_label=("level_label", "first"),
        level_center=("level_center", "first"),
        exposure=("exposure", "sum"),
        claim_amount=("y_true", "sum"),
        predicted_claim_amount=("predicted_claim_amount", "sum"),
    )
    out["observed_pure_premium"] = out["claim_amount"] / out["exposure"]
    out["predicted_pure_premium"] = out["predicted_claim_amount"] / out["exposure"]
    out["o_p_ratio"] = out["observed_pure_premium"] / out["predicted_pure_premium"]
    out = out.reset_index()
    out["level_center"] = out["level_center"].astype(float)
    return out[
        [
            "level",
            "level_label",
            "level_center",
            "exposure",
            "claim_amount",
            "predicted_claim_amount",
            "observed_pure_premium",
            "predicted_pure_premium",
            "o_p_ratio",
        ]
    ]


def _format_numeric_labels(raw: np.ndarray, codes: np.ndarray) -> np.ndarray:
    """Return a per-row interval label ``[lo, hi]`` for the bin each row belongs to."""
    labels = np.full(len(raw), "Missing", dtype=object)
    for code in np.unique(codes[codes >= 0]):
        mask = codes == code
        values = raw[mask]
        labels[mask] = f"[{values.min():g}, {values.max():g}]"
    return labels


_RATIO_EPS = 1e-12


def double_lift_table(
    y_true,
    pred_a,
    pred_b,
    sample_weight=None,
    *,
    n_bins: int = 10,
    label_a: str = "model A",
    label_b: str = "model B",
) -> pd.DataFrame:
    """Per-decile observed pure premium ordered by the ``pred_a / pred_b`` ratio.

    Policies are bucketed into exposure-weighted deciles of the ratio (high
    ratio = A predicts a higher rate relative to B), and per decile the table reports
    mean ratio, exposure, observed pure premium, and predicted pure premium
    for both A and B. Compare each predicted rate with observations within
    each ratio group; rising observations alone cannot select a model. Extreme
    ratio groups contain the largest relative disagreements, whose credibility
    depends on exposure and claims. Rates are absolute, not normalized by
    portfolio means. Use ``azoic.plots.plot_double_lift`` to render.

    Both predictions are floored at ``_RATIO_EPS`` to avoid division-by-zero
    when a GBM objective returns exact zeros (Poisson on never-claimed rows).
    """
    y_true, pred_a, w = _as_arrays(y_true, pred_a, sample_weight)
    pred_b = np.asarray(pred_b, dtype=float)
    if pred_b.shape != pred_a.shape:
        raise ValueError(f"pred_b shape {pred_b.shape} does not match pred_a shape {pred_a.shape}")
    a = np.maximum(pred_a, _RATIO_EPS)
    b = np.maximum(pred_b, _RATIO_EPS)
    ratio = a / b
    strata = make_strata(ratio, w, n_strata=n_bins)
    df = pd.DataFrame(
        {
            "y_true": y_true,
            "pred_a": pred_a,
            "pred_b": pred_b,
            "exposure": w,
            "ratio": ratio,
            "group": strata,
        }
    )
    df = df.loc[df["group"] >= 0]
    if df.empty:
        raise ValueError("no rows with finite ratio strata")
    df["predicted_claim_amount_a"] = df["pred_a"] * df["exposure"]
    df["predicted_claim_amount_b"] = df["pred_b"] * df["exposure"]
    grouped = df.groupby("group", observed=True)
    out = grouped.agg(
        mean_ratio=("ratio", "mean"),
        exposure=("exposure", "sum"),
        claim_amount=("y_true", "sum"),
        predicted_claim_amount_a=("predicted_claim_amount_a", "sum"),
        predicted_claim_amount_b=("predicted_claim_amount_b", "sum"),
    )
    out["observed_pure_premium"] = out["claim_amount"] / out["exposure"]
    out[f"{label_a}_pure_premium"] = out["predicted_claim_amount_a"] / out["exposure"]
    out[f"{label_b}_pure_premium"] = out["predicted_claim_amount_b"] / out["exposure"]
    return out.reset_index()
