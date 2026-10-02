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
    lorenz,
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
    expected = lorenz(y_true, y_true / w, w)
    np.testing.assert_allclose(oracle.get_xdata(), expected.exposure_pct)
    np.testing.assert_allclose(oracle.get_ydata(), expected.claims_pct)
    assert oracle.get_label() == f"oracle (Gini {expected.gini:.3f})"
    model_lines = lines[2:]
    assert len({line.get_color() for line in model_lines}) == 2
    labels = [line.get_label() for line in model_lines]
    assert any("glm" in label and "Gini" in label for label in labels)
    assert any("gbm" in label and "Gini" in label for label in labels)


def test_plot_lorenz_accepts_non_string_model_keys() -> None:
    """model_colors stringifies palette keys; lookups must stringify too --
    integer model ids previously raised KeyError."""
    y_true, y_pred, w = _portfolio_and_predictions()
    rng = np.random.default_rng(11)
    ax = plot_lorenz(y_true, {0: y_pred, 1: y_pred * rng.uniform(0.8, 1.2, len(y_pred))}, w)
    assert len(ax.get_lines()) == 3  # diagonal + two models
    ax2 = plot_lorenz(y_true, y_pred, w, label=0, color="#D55E00")
    assert len(ax2.get_lines()) == 2


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


@pytest.mark.parametrize("embedded", [False, True])
@pytest.mark.parametrize("all_missing", [False, True])
def test_plot_one_way_displays_missing_points_labels_and_exposure(embedded, all_missing) -> None:
    table = pd.DataFrame(
        {
            "level_label": ["20", "40", "Missing"],
            "level_center": [20, 40, np.nan],
            "observed_pure_premium": [100, 50, 2000],
            "predicted_pure_premium": [80, 60, 1500],
            "exposure": [1, 2, 5],
        }
    )
    if all_missing:
        table = table.iloc[[-1]].reset_index(drop=True)
    if embedded:
        fig, ax = plt.subplots()
        plot_one_way(table, ax=ax, exposure="background")
        exposure_ax = ax
    else:
        ax = plot_one_way(table)
        fig = ax.get_figure()
        exposure_ax = fig.axes[1]
    try:
        fig.canvas.draw()
        x = np.arange(len(table))
        for line, column in zip(
            ax.get_lines(), ["observed_pure_premium", "predicted_pure_premium"], strict=True
        ):
            np.testing.assert_allclose(line.get_xdata(), x)
            np.testing.assert_allclose(line.get_ydata(), table[column])
            assert np.isfinite(ax.transData.transform(line.get_xydata())).all()
        assert [tick.get_text() for tick in exposure_ax.get_xticklabels()] == list(
            table["level_label"]
        )
        bars = exposure_ax.patches
        np.testing.assert_allclose([bar.get_x() + bar.get_width() / 2 for bar in bars], x)
        np.testing.assert_allclose(
            [bar.get_height() for bar in bars], table["exposure"] / table["exposure"].sum()
        )
        for bar in bars:
            assert np.isfinite(bar.get_window_extent().get_points()).all()
    finally:
        plt.close(fig)


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
    assert ax.get_xlabel() == "observed pure-premium rate"


def test_plot_actual_vs_predicted_uses_rate_units(monkeypatch) -> None:
    claim_amount = np.array([2.0, 6.0, 12.0, 20.0])
    exposure = np.array([1.0, 2.0, 3.0, 4.0])
    predicted_rate = np.array([1.5, 2.5, 4.5, 5.5])
    calls = []
    original_hexbin = plt.Axes.hexbin

    def capture_hexbin(self, *args, **kwargs):
        calls.append((np.asarray(kwargs["x"]), np.asarray(kwargs["y"])))
        return original_hexbin(self, *args, **kwargs)

    monkeypatch.setattr(plt.Axes, "hexbin", capture_hexbin)
    ax = plot_actual_vs_predicted(claim_amount, predicted_rate, exposure)

    observed_rate = claim_amount / exposure
    assert len(calls) == 2
    np.testing.assert_allclose(calls[0][0], observed_rate)
    np.testing.assert_allclose(calls[0][1], predicted_rate)
    np.testing.assert_allclose(calls[1][0], predicted_rate)
    np.testing.assert_allclose(calls[1][1], observed_rate - predicted_rate)
    assert ax.get_ylabel() == "predicted pure-premium rate"
    assert ax.get_figure().axes[1].get_ylabel() == "rate residual (observed − predicted)"


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


@pytest.mark.parametrize("slot", ["y_true", "y_pred", "sample_weight"])
@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_actual_vs_predicted_rejects_nonfinite_with_limits(slot, bad) -> None:
    inputs = {
        "y_true": np.array([10.0, 20.0, 30.0]),
        "y_pred": np.array([1.0, 2.0, 3.0]),
        "sample_weight": np.ones(3),
    }
    inputs[slot][1] = bad
    with pytest.raises(ValueError, match="finite|NaN|infinity"):
        plot_actual_vs_predicted(**inputs, ax_lim=(0, 40))


@pytest.mark.parametrize("slot", ["y_true", "y_pred", "sample_weight"])
@pytest.mark.parametrize("malformed", ["short", "column", "frame", "scalar"])
def test_actual_vs_predicted_rejects_malformed_vectors(slot, malformed) -> None:
    inputs = {name: [1.0, 2.0, 3.0] for name in ("y_true", "y_pred", "sample_weight")}
    inputs[slot] = {
        "short": [1.0, 2.0],
        "column": np.ones((3, 1)),
        "frame": pd.DataFrame({"value": [1.0, 2.0, 3.0]}),
        "scalar": 1.0,
    }[malformed]
    with pytest.raises(ValueError, match="same length|inconsistent numbers|one-dimensional"):
        plot_actual_vs_predicted(**inputs, ax_lim=(0, 4))


@pytest.mark.parametrize("exposure", [[0, 1, 1], [-1, 1, 1]])
def test_actual_vs_predicted_requires_positive_exposure(exposure) -> None:
    with pytest.raises(ValueError, match="positive|non-negative"):
        plot_actual_vs_predicted([1, 2, 3], [1, 2, 3], exposure, ax_lim=(0, 4))


def test_actual_vs_predicted_rejects_negative_claims() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        plot_actual_vs_predicted([1, -2, 3], [1, 2, 3], ax_lim=(0, 4))


@pytest.mark.parametrize("weighted", [False, True])
def test_actual_vs_predicted_preserves_density_totals(monkeypatch, weighted) -> None:
    claims = np.array([0.0, 2.0, 30.0])
    prediction = pd.Series([1.0, 2.0, 3.0])
    exposure = pd.Series([0.1, 1.0, 2.0]) if weighted else None
    weights = exposure.to_numpy() if weighted else np.ones(3)
    calls = []
    original_hexbin = plt.Axes.hexbin

    def capture_hexbin(self, *args, **kwargs):
        calls.append(kwargs)
        return original_hexbin(self, *args, **kwargs)

    monkeypatch.setattr(plt.Axes, "hexbin", capture_hexbin)
    ax = plot_actual_vs_predicted(pd.Series(claims), prediction, exposure, bins=None)
    np.testing.assert_allclose(calls[0]["x"] * weights, claims)
    np.testing.assert_allclose(calls[1]["y"], claims / weights - prediction)
    for panel in [ax, ax.get_figure().axes[1]]:
        assert panel.collections[0].get_array().sum() == pytest.approx(weights.sum())


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


@pytest.mark.parametrize(
    "claims, exposure, expected_gini",
    [
        ([100, 20], [1, 0.1], 0.0757575757575758),
        ([100, 20], None, 1 / 3),
        ([100, 20], [1, 1], 1 / 3),
        ([100, 50, 200], [1, 0.5, 1], 6 / 35),
    ],
)
def test_plot_lorenz_oracle_ranks_observed_rates(claims, exposure, expected_gini) -> None:
    claims = np.asarray(claims, dtype=float)
    weights = np.ones_like(claims) if exposure is None else np.asarray(exposure)
    expected = lorenz(claims, claims / weights, weights)
    assert expected.gini == pytest.approx(expected_gini)
    ax = plot_lorenz(claims, np.ones_like(claims), exposure, show_oracle=True)
    oracle = ax.get_lines()[1]
    np.testing.assert_allclose(oracle.get_xdata(), expected.exposure_pct)
    np.testing.assert_allclose(oracle.get_ydata(), expected.claims_pct)
    assert oracle.get_label() == f"oracle (Gini {expected_gini:.3f})"
    if len(claims) == 3:
        np.testing.assert_allclose(oracle.get_xdata(), [0, 0.6, 1])
        np.testing.assert_allclose(oracle.get_ydata(), [0, 3 / 7, 1])


@pytest.mark.parametrize("weighted", [False, True])
@pytest.mark.parametrize("embedded", [False, True])
@pytest.mark.parametrize("logx", [False, True])
@pytest.mark.parametrize("logy", [False, True])
def test_residual_scale_keeps_signed_density_visible(weighted, embedded, logx, logy) -> None:
    prediction = np.array([110.0, 120.0, 130.0])
    residual = np.array([-100.0, 0.0, 100.0])
    exposure = np.array([0.5, 1.0, 2.0]) if weighted else None
    claims = (prediction + residual) * (exposure if weighted else 1)
    caller = None
    if embedded:
        _, axes = plt.subplots(1, 2, figsize=(11, 4.5))
        axes[1].remove()
        caller = axes[0]
    ax = plot_actual_vs_predicted(
        claims, prediction, exposure, gridsize=8, bins="log", logx=logx, logy=logy, ax=caller
    )
    fig = ax.get_figure()
    residual_ax = ax.child_axes[0] if embedded else fig.axes[1]
    fig.canvas.draw()
    if embedded:
        assert ax is caller
    assert ax.get_xscale() == residual_ax.get_xscale() == ("log" if logx else "linear")
    assert ax.get_yscale() == ("log" if logy else "linear")
    points = np.column_stack([prediction, residual])
    displayed = residual_ax.transData.transform(points)
    assert np.isfinite(displayed).all()
    assert np.all(np.diff(displayed[:, 1]) > 0)
    assert all(residual_ax.bbox.contains(*point) for point in displayed)
    assert all(fig.bbox.contains(*point) for point in displayed)
    density = residual_ax.collections[0]
    local_centres = np.array(
        [
            (path.vertices.min(axis=0) + path.vertices.max(axis=0)) / 2
            for path in density.get_paths()
        ]
    )
    centres = local_centres + density.get_offsets()
    np.testing.assert_allclose(np.sort(centres[:, 1]), residual)
    assert np.isfinite(density.get_array()).all()
    assert density.get_array().sum() == pytest.approx(exposure.sum() if weighted else 3)
    assert isinstance(density.norm, matplotlib.colors.LogNorm)
    rendered_centres = density.get_transform().transform(local_centres) + (
        density.get_offset_transform().transform(density.get_offsets())
    )
    np.testing.assert_allclose(rendered_centres, residual_ax.transData.transform(centres))
    assert np.isfinite(rendered_centres).all()
    assert np.all(np.diff(rendered_centres[np.argsort(centres[:, 1]), 1]) > 0)
    assert all(residual_ax.bbox.contains(*point) for point in rendered_centres)
    assert all(fig.bbox.contains(*point) for point in rendered_centres)
    assert residual_ax.get_yscale() == ("symlog" if logy else "linear")
    if logy:
        assert residual_ax.yaxis.get_transform().linthresh == 2
