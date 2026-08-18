"""Actuarial diagnostic plots: Lorenz, lift, calibration, one-way, double-lift.

All chart functions accept ``ax=`` to embed in a caller figure and ``path=``
to save a PNG. ``ax=None`` triggers a guided layout built with
``matplotlib.pyplot.subplot_mosaic`` (bottom exposure panel where useful).

Style is fivethirtyeight layered with :data:`AZOIC_STYLE` (CVD-safe Okabe-Ito
palette, white background, subtle grid); every function applies it to its own
figure, and :func:`azoic_style` lets callers style embedded grids identically.
Observed quantities are always the same grey (:data:`OBSERVED`); each model
keeps one color across all charts via :func:`model_colors`.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from cycler import cycler
from matplotlib.figure import Figure, SubFigure

from azoic.metrics import lorenz

__all__ = [
    "AZOIC_STYLE",
    "OKABE_ITO",
    "OBSERVED",
    "EXPOSURE",
    "azoic_style",
    "model_colors",
    "plot_lorenz",
    "plot_lift",
    "plot_calibration",
    "plot_one_way",
    "plot_double_lift",
    "plot_actual_vs_predicted",
]

OKABE_ITO = [
    "#E69F00",
    "#56B4E9",
    "#009E73",
    "#D55E00",
    "#0072B2",
    "#CC79A7",
]
OBSERVED = "#6E6E6E"
EXPOSURE = "0.75"
_DIAGONAL = "0.45"

AZOIC_STYLE: dict[str, Any] = {
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
    "axes.edgecolor": "0.30",
    "axes.linewidth": 0.9,
    "axes.labelcolor": "0.15",
    "axes.labelsize": 11,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.titlepad": 10,
    "axes.prop_cycle": cycler(color=OKABE_ITO),
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.color": "0.85",
    "grid.linewidth": 0.8,
    "text.color": "0.15",
    "font.size": 11,
    "xtick.color": "0.25",
    "ytick.color": "0.25",
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.frameon": False,
    "legend.fontsize": 10,
    "lines.linewidth": 2.0,
    "savefig.dpi": 120,
}


@contextmanager
def azoic_style():
    """Apply the azoic chart style (fivethirtyeight base + CVD-safe overrides)."""
    with plt.style.context(["fivethirtyeight", AZOIC_STYLE]):
        yield


def model_colors(names) -> dict[str, str]:
    """Stable Okabe-Ito color per model name, consistent across all charts."""
    return {str(name): OKABE_ITO[i % len(OKABE_ITO)] for i, name in enumerate(names)}


def _save(fig: Figure | SubFigure | None, path: str | Path | None) -> None:
    if path is None:
        return
    target = fig.figure if isinstance(fig, SubFigure) else fig
    if isinstance(target, Figure):
        target.savefig(str(path), dpi=120, bbox_inches="tight")


def _draw_colorbar(mappable: Any, *, target_axes: plt.Axes, label: str) -> None:
    """Attach a colorbar to ``target_axes`` no matter which figure parent holds it."""
    target = target_axes.get_figure()
    if isinstance(target, SubFigure):
        target = target.figure
    if isinstance(target, Figure):
        target.colorbar(mappable, ax=target_axes, label=label)


def _bar_width(x: np.ndarray) -> float:
    if len(x) < 2:
        return 0.8
    diffs = np.diff(np.sort(x))
    diffs = diffs[diffs > 0]
    if len(diffs) == 0:
        return 0.8
    return float(min(np.median(diffs) * 0.9, 0.8))


def _exposure_share(table: pd.DataFrame) -> np.ndarray:
    e = table["exposure"].to_numpy(dtype=float)
    total = float(e.sum())
    return e / total if total > 0 else e


def _background_exposure(ax: plt.Axes, x: np.ndarray, share: np.ndarray) -> None:
    ax.bar(
        x,
        share,
        width=_bar_width(x),
        color=EXPOSURE,
        alpha=0.35,
        edgecolor="none",
        zorder=0,
    )


def _standalone_with_panel(
    figsize: tuple[float, float],
) -> tuple[plt.Figure, plt.Axes, plt.Axes]:
    fig, axd = plt.subplot_mosaic(
        [["chart"], ["exposure"]],
        figsize=figsize,
        height_ratios=[3, 1],
        sharex=True,
    )
    return fig, axd["chart"], axd["exposure"]


def _draw_exposure_panel(panel: plt.Axes, x: np.ndarray, share: np.ndarray) -> None:
    panel.bar(
        x,
        share,
        width=_bar_width(x),
        color=EXPOSURE,
        alpha=0.9,
        edgecolor="none",
    )
    panel.set_ylabel("Exposure share")
    panel.set_ylim(0, float(share.max()) * 1.2 if share.max() > 0 else 1.0)


def plot_lorenz(
    y_true,
    y_pred,
    sample_weight=None,
    *,
    ax: plt.Axes | None = None,
    path: str | Path | None = None,
    title: str = "Lorenz curve",
    label: str = "model",
    color: str | None = None,
    show_oracle: bool = False,
    show_shade: bool = False,
) -> plt.Axes:
    """Plot exposure-vs-claims concentration curves, one color per model.

    ``y_pred`` is a single prediction array or a mapping ``{model_name:
    predictions}``. The diagonal (random ranking) is drawn exactly once; with
    ``show_oracle=True`` the perfect-ranking curve (``y_pred == y_true``) is
    overlaid once as a grey dash-dot reference. Curves are sorted from safest
    to riskiest (ascending prediction) and sit below the diagonal for any
    model that ranks risk better than random; the Gini per model appears in
    the legend.
    """
    with azoic_style():
        if ax is None:
            fig, ax = plt.subplots(figsize=(6.5, 5))
        else:
            fig = ax.get_figure()
        curves = dict(y_pred) if isinstance(y_pred, Mapping) else {label: y_pred}
        palette = model_colors(curves)
        if color is not None and len(curves) == 1:
            palette[next(iter(curves))] = color
        ax.plot(
            [0, 1],
            [0, 1],
            linestyle=":",
            color=_DIAGONAL,
            linewidth=1.2,
            label="random (diagonal)",
        )
        if show_oracle:
            oracle = lorenz(y_true, np.asarray(y_true, dtype=float), sample_weight)
            ax.plot(
                oracle.exposure_pct,
                oracle.claims_pct,
                linestyle="-.",
                color=OBSERVED,
                linewidth=1.4,
                label=f"oracle (Gini {oracle.gini:.3f})",
            )
        for name, pred in curves.items():
            res = lorenz(y_true, pred, sample_weight)
            if show_shade and len(curves) == 1:
                ax.fill_between(
                    res.exposure_pct,
                    res.claims_pct,
                    res.exposure_pct,
                    color=palette[name],
                    alpha=0.18,
                    label="_nolegend_",
                )
            ax.plot(
                res.exposure_pct,
                res.claims_pct,
                color=palette[name],
                linewidth=2.2,
                label=f"{name} (Gini {res.gini:.3f})",
            )
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xlabel("Cumulative exposure share (safest → riskiest)")
        ax.set_ylabel("Cumulative observed loss share")
        ax.set_title(title)
        ax.legend(loc="upper left")
        _save(fig, path)
        return ax


def plot_lift(
    table,
    *,
    color: str | None = None,
    label: str = "predicted",
    ax: plt.Axes | None = None,
    path: str | Path | None = None,
    title: str = "Lift chart",
    exposure: Literal["background", "none"] = "background",
    logy: bool = False,
) -> plt.Axes:
    """Observed vs predicted pure premium per exposure-balanced decile.

    ``table`` is the output of ``azoic.metrics.calibration_table`` (deciles of
    predicted risk by default). Observed is the grey ``o-`` line, predicted
    the model-colored ``s--`` line: the two should track in level
    (calibration) while observed rises with the decile (ranking); crossings
    expose deciles where the model over- or under-prices. Translucent
    background bars show the exposure share per decile (sklearn-example
    style).
    """
    with azoic_style():
        if ax is None:
            fig, ax = plt.subplots(figsize=(6.5, 4.5))
        else:
            fig = ax.get_figure()
        x = np.arange(1, len(table) + 1)
        observed = table["observed_pure_premium"].to_numpy(dtype=float)
        predicted = table["predicted_pure_premium"].to_numpy(dtype=float)
        if exposure == "background":
            _background_exposure(ax, x, _exposure_share(table))
        ax.plot(x, observed, marker="o", color=OBSERVED, label="observed")
        ax.plot(
            x,
            predicted,
            marker="s",
            linestyle="--",
            color=color if color is not None else OKABE_ITO[0],
            label=label,
        )
        ax.set_xticks(x)
        ax.set_xlabel("Decile of predicted risk (low → high)")
        ax.set_ylabel("Pure premium")
        ax.set_title(title)
        ax.legend(loc="upper left")
        if logy:
            ax.set_yscale("log")
        _save(fig, path)
        return ax


def _calibration_scatter(ax: plt.Axes, table: pd.DataFrame) -> None:
    pred = table["predicted_pure_premium"].to_numpy(dtype=float)
    obs = table["observed_pure_premium"].to_numpy(dtype=float)
    exp = table["exposure"].to_numpy(dtype=float)
    sizes = 15 + 150 * (exp / exp.max() if exp.max() > 0 else np.zeros_like(exp))
    ax.scatter(pred, obs, s=sizes, color=OBSERVED, alpha=0.6, edgecolor="none")
    lo = float(min(pred.min(), obs.min()))
    hi = float(max(pred.max(), obs.max()))
    pad = 0.05 * (hi - lo if hi > lo else 1.0)
    lims = (lo - pad, hi + pad)
    ax.plot(lims, lims, "--", color="black", linewidth=1.2, label="perfect (y=x)")
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_xlabel("Predicted pure premium")
    ax.set_ylabel("Observed pure premium")
    ax.legend(loc="upper left")


def plot_calibration(
    table,
    *,
    ax: plt.Axes | None = None,
    path: str | Path | None = None,
    title: str = "Calibration",
    logx: bool = False,
    logy: bool = False,
) -> plt.Axes:
    """Scatter of observed vs predicted pure premium per segment.

    ``table`` is the output of ``azoic.metrics.calibration_table``. Point size
    is proportional to segment exposure; the dashed y=x line is perfect
    calibration. The decile-level observed-vs-paired view lives in
    :func:`plot_lift`.
    """
    with azoic_style():
        if ax is None:
            fig, ax = plt.subplots(figsize=(6, 6))
        else:
            fig = ax.get_figure()
        _calibration_scatter(ax, table)
        if logx:
            ax.set_xscale("log")
        if logy:
            ax.set_yscale("log")
        ax.set_title(title)
        _save(fig, path)
        return ax


def plot_one_way(
    table,
    *,
    color: str | None = None,
    label: str = "predicted",
    ax: plt.Axes | None = None,
    path: str | Path | None = None,
    title: str = "One-way observed vs predicted",
    xlabel: str = "Feature value",
    exposure: Literal["panel", "background", "none"] = "panel",
    logy: bool = False,
) -> plt.Axes:
    """Per-level observed vs predicted pure premium with the exposure layout.

    Use the output of ``azoic.metrics.one_way_table``. With ``n_bins=None``
    the table has one level per unique value (natural numeric axis: driver
    age has as many points as distinct test values). Observed is the grey
    ``o-`` line, predicted the model-colored ``s--`` line. Stand-alone
    (``ax=None``, default ``exposure="panel"``) a bottom exposure-share panel
    is drawn via ``subplot_mosaic``; pass ``exposure="background"`` when
    embedding in a caller grid to underlay translucent exposure bars instead.
    """
    with azoic_style():
        obs = table["observed_pure_premium"].to_numpy(dtype=float)
        pred = table["predicted_pure_premium"].to_numpy(dtype=float)
        centers = table.get("level_center", pd.Series(np.nan)).to_numpy(dtype=float)
        labels = table.get("level_label", pd.Series(range(len(obs)))).astype(str).tolist()
        is_numeric = np.isfinite(centers).any()
        x = centers if is_numeric else np.arange(len(obs))
        share = _exposure_share(table)
        if ax is None:
            if exposure == "panel":
                fig, main, panel = _standalone_with_panel((6.5, 5.0))
                ax = main
            else:
                fig, ax = plt.subplots(figsize=(6.5, 4.5))
                panel = None
        else:
            fig = ax.get_figure()
            panel = None
        if exposure == "background":
            _background_exposure(ax, x, share)
        ax.plot(x, obs, marker="o", color=OBSERVED, label="observed")
        ax.plot(
            x,
            pred,
            marker="s",
            linestyle="--",
            color=color if color is not None else OKABE_ITO[0],
            label=label,
        )
        if is_numeric:
            ax.set_xlabel(xlabel)
        else:
            ax.set_xticks(np.arange(len(obs)))
            ax.set_xticklabels(labels, rotation=45, ha="right")
            ax.set_xlabel("Level")
        ax.set_ylabel("Pure premium")
        ax.set_title(title)
        ax.legend(loc="upper left")
        if logy:
            ax.set_yscale("log")
        if panel is not None:
            _draw_exposure_panel(panel, x, share)
        _save(fig, path)
        return ax


def plot_double_lift(
    table,
    *,
    ax: plt.Axes | None = None,
    path: str | Path | None = None,
    label_a: str = "model A",
    label_b: str = "model B",
    color_a: str | None = None,
    color_b: str | None = None,
    title: str = "Double-lift chart",
    exposure: Literal["panel", "background", "none"] = "panel",
    logy: bool = False,
) -> plt.Axes:
    """Per-decile observed pure premium, ordered by the ``pred_a / pred_b`` ratio.

    ``table`` is the output of ``azoic.metrics.double_lift_table``. Three
    lines: observed (grey ``o-``), predicted A (``s--``), predicted B
    (``^:``), one color per model, per ratio decile (mean ratio on tick
    labels). Rising observed across deciles favours A; falling favours B;
    the middle deciles carry the most diagnostic signal. Stand-alone draws a
    bottom exposure panel; embedded grids get background bars.
    """
    with azoic_style():
        x = np.arange(len(table))
        share = _exposure_share(table)
        if ax is None:
            if exposure == "panel":
                fig, main, panel = _standalone_with_panel((7, 5.0))
                ax = main
            else:
                fig, ax = plt.subplots(figsize=(7, 4.5))
                panel = None
        else:
            fig = ax.get_figure()
            panel = None
        if exposure == "background":
            _background_exposure(ax, x, share)
        ax.plot(
            x,
            table["observed_pure_premium"].to_numpy(dtype=float),
            marker="o",
            color=OBSERVED,
            label="observed",
        )
        ax.plot(
            x,
            table[f"{label_a}_pure_premium"].to_numpy(dtype=float),
            marker="s",
            linestyle="--",
            color=color_a if color_a is not None else OKABE_ITO[0],
            label=label_a,
        )
        ax.plot(
            x,
            table[f"{label_b}_pure_premium"].to_numpy(dtype=float),
            marker="^",
            linestyle=":",
            color=color_b if color_b is not None else OKABE_ITO[1],
            label=label_b,
        )
        ax.set_xticks(x)
        ax.set_xticklabels(
            [f"{r:.2f}" for r in table["mean_ratio"].to_numpy(dtype=float)],
            rotation=45,
            ha="right",
        )
        ax.set_xlabel("Ratio decile (mean pred_A / pred_B)")
        ax.set_ylabel("Pure premium")
        ax.set_title(title)
        ax.legend(loc="upper left")
        if logy:
            ax.set_yscale("log")
        if panel is not None:
            _draw_exposure_panel(panel, x, share)
        _save(fig, path)
        return ax


def _as_float_array(values) -> np.ndarray:
    return np.asarray(
        values.to_numpy().ravel() if hasattr(values, "to_numpy") else values,
        dtype=float,
    )


def plot_actual_vs_predicted(
    y_true,
    y_pred,
    sample_weight=None,
    *,
    bins: Literal["log"] | int | None = "log",
    gridsize: int = 50,
    cmap: str | None = None,
    ax_lim: tuple[float, float] | None = None,
    logx: bool = False,
    logy: bool = False,
    ax: plt.Axes | None = None,
    path: str | Path | None = None,
    title: str = "Actual vs predicted",
) -> plt.Axes:
    """Hexbin density of observed vs predicted with a residual hexbin panel.

    Left panel: observed on x, predicted on y, y=x dashed reference. Right
    panel: residuals (observed − predicted) vs predicted with a zero
    reference. Density colouring is exposure-weighted (Σ exposure per hex)
    when ``sample_weight`` is supplied, otherwise log counts; the two panels
    get independent colorbars. ``cividis`` by default (CVD-safe).
    """
    with azoic_style():
        cmap = "cividis" if cmap is None else cmap
        y_true = _as_float_array(y_true)
        y_pred = _as_float_array(y_pred)
        if sample_weight is not None:
            sample_weight = _as_float_array(sample_weight)
        if ax is None:
            fig, axd = plt.subplot_mosaic([["scatter", "residual"]], figsize=(11, 4.5))
            ax_scatter, ax_resid = axd["scatter"], axd["residual"]
        else:
            fig = ax.get_figure()
            ax_scatter = ax
            ax_resid = ax.inset_axes((1.04, 0.0, 1.0, 1.0))
        if sample_weight is not None:
            hb = ax_scatter.hexbin(
                x=y_true,
                y=y_pred,
                C=sample_weight,
                reduce_C_function=np.sum,
                gridsize=gridsize,
                cmap=cmap,
                bins=bins,
                mincnt=1,
            )
            cb_label = "Σ exposure"
        else:
            hb = ax_scatter.hexbin(
                x=y_true,
                y=y_pred,
                gridsize=gridsize,
                cmap=cmap,
                bins=bins,
                mincnt=1,
            )
            cb_label = "log₁₀(count)" if bins == "log" else "count"
        if ax_lim is not None:
            lo, hi = ax_lim
            ax_scatter.set_xlim(lo, hi)
            ax_scatter.set_ylim(lo, hi)
            ref_x = np.linspace(lo, hi, 100)
        else:
            ref_x = np.linspace(float(y_true.min()), float(y_true.max()), 100)
            ax_scatter.set_xlim(ref_x[0], ref_x[-1])
            ax_scatter.set_ylim(float(y_pred.min()), float(y_pred.max()))
        ax_scatter.plot(ref_x, ref_x, "--", color="black", linewidth=1.2, label="y = x")
        ax_scatter.set_xlabel("observed")
        ax_scatter.set_ylabel("predicted")
        ax_scatter.set_title(f"{title} — scatter")
        _draw_colorbar(hb, target_axes=ax_scatter, label=cb_label)
        if sample_weight is not None:
            hb2 = ax_resid.hexbin(
                x=y_pred,
                y=y_true - y_pred,
                C=sample_weight,
                reduce_C_function=np.sum,
                gridsize=gridsize,
                cmap=cmap,
                bins=bins,
                mincnt=1,
            )
        else:
            hb2 = ax_resid.hexbin(
                x=y_pred,
                y=y_true - y_pred,
                gridsize=gridsize,
                cmap=cmap,
                bins=bins,
                mincnt=1,
            )
        ax_resid.axhline(0.0, color="black", linewidth=1.2, linestyle="--")
        ax_resid.set_xlabel("predicted")
        ax_resid.set_ylabel("residual (observed − predicted)")
        ax_resid.set_title(f"{title} — residuals")
        _draw_colorbar(hb2, target_axes=ax_resid, label=cb_label)
        if logx:
            ax_scatter.set_xscale("log")
            ax_resid.set_xscale("log")
        if logy:
            ax_scatter.set_yscale("log")
            ax_resid.set_yscale("log")
        _save(fig, path)
        return ax_scatter
