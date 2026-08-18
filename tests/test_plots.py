"""Tests for azoic.plots: style registry, lorenz / lift / calibration / one-way
/ double-lift / hexbin render headless.

The Agg backend is forced before importing azoic.plots so pyplot never
tries to open a display (PRD M4 done-when: figures render headless to PNG).
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from azoic.metrics import (  # noqa: E402
    calibration_table,
    double_lift_table,
    one_way_table,
)
from azoic.plots import (  # noqa: E402
    OBSERVED,
    OKABE_ITO,
    azoic_style,
    model_colors,
    plot_actual_vs_predicted,
    plot_calibration,
    plot_double_lift,
    plot_lift,
    plot_lorenz,
    plot_one_way,
)


def _portfolio_and_predictions(seed: int = 7, n: int = 4000):
    """Synthetic continuous y_true, y_pred, sample_weight for plot logic tests.

    The real synthetic_portfolio's pure premium has a huge zero mass (most
    policies have no claims), so exposure-balanced deciles would collapse --
    these tests exercise *plot logic* (deciles, line counts, savefile), not
    actuarial behaviour. Random exponential y with a noisy y_pred gives 10
    distinct deciles and a positive Gini.
    """
    rng = np.random.default_rng(seed)
    y_true = rng.exponential(scale=1.0, size=n)
    y_pred = y_true * rng.uniform(0.5, 1.5, size=n)
    w = rng.uniform(0.5, 1.0, size=n)
    return y_true, y_pred, w


def test_azoic_style_applies_and_restores() -> None:
    original = plt.rcParams["figure.facecolor"]
    with azoic_style():
        assert plt.rcParams["figure.facecolor"] == "white"
        cycle_colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
        assert cycle_colors == OKABE_ITO
        assert plt.rcParams["legend.frameon"] is False
    assert plt.rcParams["figure.facecolor"] == original
    assert plt.rcParams["axes.prop_cycle"].by_key()["color"] != OKABE_ITO


def test_model_colors_stable_and_distinct() -> None:
    names = ["glm", "gbm", "fs-glm", "fs-gbm"]
    colors = model_colors(names)
    assert list(colors) == names
    assert len(set(colors.values())) == len(names)
    assert all(c in OKABE_ITO for c in colors.values())
    assert model_colors(names) == colors
    assert model_colors([*names, "extra"])["glm"] == colors["glm"]


def test_plot_lorenz_writes_png_and_returns_axes(tmp_path) -> None:
    y_true, y_pred, w = _portfolio_and_predictions()
    out = tmp_path / "lorenz.png"
    ax = plot_lorenz(y_true, y_pred, w, path=out)
    assert isinstance(ax, plt.Axes)
    assert out.exists()
    assert out.stat().st_size > 500
    assert len(ax.get_lines()) == 2
    assert ax.get_xlim()[0] >= 0.0 and ax.get_xlim()[1] <= 1.0


def test_plot_lorenz_accepts_caller_axes() -> None:
    y_true, y_pred, w = _portfolio_and_predictions()
    fig, ax = plt.subplots()
    returned = plot_lorenz(y_true, y_pred, w, ax=ax)
    assert returned is ax


def test_plot_lorenz_multi_model_single_diagonal_and_oracle() -> None:
    y_true, y_pred, w = _portfolio_and_predictions()
    rng = np.random.default_rng(11)
    predictions = {
        "glm": y_pred,
        "gbm": y_pred * rng.uniform(0.8, 1.2, size=len(y_pred)),
    }
    ax = plot_lorenz(y_true, predictions, w, show_oracle=True)
    lines = ax.get_lines()
    assert len(lines) == 4  # diagonal + oracle + two models, each drawn once
    diagonal = lines[0]
    assert "random" in diagonal.get_label()
    assert diagonal.get_linestyle() == ":"
    oracle = lines[1]
    assert "oracle" in oracle.get_label()
    model_lines = lines[2:]
    assert len({line.get_color() for line in model_lines}) == 2
    labels = [line.get_label() for line in model_lines]
    assert any("glm" in label and "Gini" in label for label in labels)
    assert any("gbm" in label and "Gini" in label for label in labels)


def test_plot_lorenz_single_model_shade() -> None:
    y_true, y_pred, w = _portfolio_and_predictions()
    ax = plot_lorenz(y_true, y_pred, w, show_shade=True, color="#D55E00")
    assert len(ax.get_lines()) == 2
    has_poly = any(
        p.__class__.__name__ in {"PolyCollection", "FillBetweenPolyCollection"}
        for p in ax.get_children()
    )
    assert has_poly


def test_plot_lift_lines_observed_and_predicted(tmp_path) -> None:
    y_true, y_pred, w = _portfolio_and_predictions()
    tbl = calibration_table(y_true, y_pred, w, n_bins=10)
    out = tmp_path / "lift.png"
    ax = plot_lift(tbl, color="#009E73", label="gbm", path=out)
    assert out.exists() and out.stat().st_size > 500
    lines = ax.get_lines()
    assert len(lines) == 2
    observed, predicted = lines
    assert observed.get_label() == "observed"
    assert observed.get_color() == OBSERVED
    assert predicted.get_label() == "gbm"
    assert predicted.get_color() == "#009E73"
    np.testing.assert_allclose(observed.get_ydata(), tbl["observed_pure_premium"].to_numpy())
    np.testing.assert_allclose(predicted.get_ydata(), tbl["predicted_pure_premium"].to_numpy())
    assert np.allclose(observed.get_xdata(), np.arange(1, 11))
    assert any(getattr(p, "get_zorder", lambda: 1)() == 0 for p in ax.patches)


def test_plot_lift_background_exposure_optional() -> None:
    y_true, y_pred, w = _portfolio_and_predictions()
    tbl = calibration_table(y_true, y_pred, w, n_bins=8)
    fig, ax = plt.subplots()
    plot_lift(tbl, ax=ax, exposure="none")
    assert len(ax.get_lines()) == 2
    assert list(ax.patches) == []


def test_plot_calibration_scatter_only(tmp_path) -> None:
    y_true, y_pred, w = _portfolio_and_predictions()
    tbl = calibration_table(y_true, y_pred, w, n_bins=10)
    out = tmp_path / "calibration.png"
    ax = plot_calibration(tbl, path=out)
    assert out.exists() and out.stat().st_size > 500
    assert len(ax.collections) == 1
    assert len(ax.get_lines()) == 1
    assert "perfect" in ax.get_lines()[0].get_label()


def test_plot_one_way_standalone_has_exposure_panel(tmp_path) -> None:
    y_true, y_pred, w = _portfolio_and_predictions()
    X = pd.DataFrame({"driver_age": np.random.default_rng(0).integers(18, 90, size=len(y_true))})
    tbl = one_way_table(X, "driver_age", y_true, y_pred, w, n_bins=8)
    out = tmp_path / "oneway.png"
    ax = plot_one_way(tbl, path=out)
    assert out.exists() and out.stat().st_size > 500
    fig = ax.get_figure()
    assert len(fig.axes) == 2
    main_ax, expo_ax = fig.axes
    assert len(main_ax.get_lines()) == 2
    assert expo_ax.get_ylabel() == "Exposure share"
    assert len(expo_ax.patches) == 8


def test_plot_one_way_unique_values_one_point_per_value() -> None:
    y_true, y_pred, w = _portfolio_and_predictions()
    rng = np.random.default_rng(5)
    ages = rng.integers(18, 40, size=len(y_true))
    X = pd.DataFrame({"driver_age": ages})
    tbl = one_way_table(X, "driver_age", y_true, y_pred, w, n_bins=None)
    assert len(tbl) == np.unique(ages).size
    ax = plot_one_way(tbl)
    observed = ax.get_lines()[0]
    np.testing.assert_allclose(observed.get_xdata(), tbl["level_center"].to_numpy(dtype=float))


def test_plot_one_way_categorical_uses_level_labels() -> None:
    y_true, y_pred, w = _portfolio_and_predictions()
    X = pd.DataFrame(
        {
            "region": np.random.default_rng(1).choice(
                ["urban", "suburban", "rural"], size=len(y_true)
            )
        }
    )
    tbl = one_way_table(X, "region", y_true, y_pred, w)
    ax = plot_one_way(tbl)
    fig = ax.get_figure()
    all_labels = set()
    for axis in fig.axes:
        all_labels.update(t.get_text() for t in axis.get_xticklabels())
    assert {"urban", "suburban", "rural"}.issubset(all_labels)


def test_plot_one_way_embedded_background_exposure() -> None:
    y_true, y_pred, w = _portfolio_and_predictions()
    X = pd.DataFrame({"driver_age": np.random.default_rng(2).integers(18, 90, size=len(y_true))})
    tbl = one_way_table(X, "driver_age", y_true, y_pred, w, n_bins=5)
    fig, ax = plt.subplots()
    returned = plot_one_way(tbl, ax=ax, exposure="background", color="#0072B2")
    assert returned is ax
    assert len(fig.axes) == 1
    assert len(ax.get_lines()) == 2
    assert ax.get_lines()[1].get_color() == "#0072B2"
    assert any(getattr(p, "get_zorder", lambda: 1)() == 0 for p in ax.patches)


def _double_lift_table(seed: int, n_bins: int):
    y_true, y_pred, w = _portfolio_and_predictions()
    pred_b = y_pred * np.random.default_rng(seed).uniform(0.7, 1.3, size=len(y_true))
    return double_lift_table(
        y_true, y_pred, pred_b, w, n_bins=n_bins, label_a="champion", label_b="benchmark"
    )


def test_plot_double_lift_writes_png(tmp_path) -> None:
    tbl = _double_lift_table(3, 8)
    out = tmp_path / "double.png"
    ax = plot_double_lift(
        tbl,
        path=out,
        label_a="champion",
        label_b="benchmark",
        color_a="#E69F00",
        color_b="#56B4E9",
    )
    assert out.exists() and out.stat().st_size > 500
    lines = ax.get_lines()
    assert len(lines) == 3
    observed, line_a, line_b = lines
    assert observed.get_color() == OBSERVED
    assert line_a.get_color() == "#E69F00"
    assert line_b.get_color() == "#56B4E9"
    assert {line.get_label() for line in lines} == {"observed", "champion", "benchmark"}


def test_plot_double_lift_standalone_has_exposure_panel() -> None:
    tbl = _double_lift_table(3, 6)
    ax = plot_double_lift(tbl, label_a="champion", label_b="benchmark")
    fig = ax.get_figure()
    assert len(fig.axes) == 2
    assert len(ax.get_lines()) == 3


def test_plot_double_lift_accepts_caller_axes() -> None:
    tbl = _double_lift_table(4, 5)
    fig, ax = plt.subplots()
    returned = plot_double_lift(tbl, ax=ax, label_a="champion", label_b="benchmark")
    assert returned is ax


def test_plot_actual_vs_predicted_unweighted(tmp_path) -> None:
    y_true, y_pred, _ = _portfolio_and_predictions()
    out = tmp_path / "actpred.png"
    ax = plot_actual_vs_predicted(y_true, y_pred, path=out)
    assert out.exists() and out.stat().st_size > 500
    fig = ax.get_figure()
    panel_axes = [a for a in fig.axes if a.get_title() and "Actual vs predicted" in a.get_title()]
    assert len(panel_axes) == 2
    assert ax.get_xlabel() == "observed"


def test_plot_actual_vs_predicted_exposure_weighted() -> None:
    y_true, y_pred, w = _portfolio_and_predictions()
    ax = plot_actual_vs_predicted(y_true, y_pred, w)
    fig = ax.get_figure()
    panel_axes = [a for a in fig.axes if a.get_title() and "Actual vs predicted" in a.get_title()]
    assert len(panel_axes) == 2
    cbar_count = sum(len(a.collections) for a in panel_axes)
    assert cbar_count >= 2


def test_plot_actual_vs_predicted_log_axes() -> None:
    y_true, y_pred, _ = _portfolio_and_predictions()
    ax = plot_actual_vs_predicted(y_true, y_pred, logx=True, logy=True)
    assert ax.get_xscale() == "log"
    assert ax.get_yscale() == "log"


def test_plot_actual_vs_predicted_with_ax_lim() -> None:
    y_true, y_pred, _ = _portfolio_and_predictions()
    ax = plot_actual_vs_predicted(y_true, y_pred, ax_lim=(0.0, 5.0))
    assert ax.get_xlim() == (0.0, 5.0)
    assert ax.get_ylim() == (0.0, 5.0)


def test_all_charts_round_trip_headless(tmp_path) -> None:
    y_true, y_pred, w = _portfolio_and_predictions()
    tbl = calibration_table(y_true, y_pred, w, n_bins=8)
    plot_lorenz(y_true, {"m1": y_pred, "m2": y_pred * 1.1}, w, path=tmp_path / "l.png")
    plot_lift(tbl, path=tmp_path / "lift.png")
    plot_calibration(tbl, path=tmp_path / "cal.png")
    for name in ("l.png", "lift.png", "cal.png"):
        out = tmp_path / name
        assert out.exists() and out.stat().st_size > 500
    plt.close("all")


@pytest.fixture(autouse=True)
def _close_figures():
    yield
    plt.close("all")
