# Diagnostics and visualization

Azoic keeps calculation and rendering separate: functions in `azoic.metrics`
return reusable values or pandas tables, while `azoic.plots` renders those
results with matplotlib.

Assume `test` contains aggregate `claim_amount` and `exposure`, and two fitted
models produced pure-premium rates `pred_glm` and `pred_gbm`:

```python
from azoic.metrics import calibration_table, double_lift_table, one_way_table

y_true = test["claim_amount"].to_numpy()
exposure = test["exposure"].to_numpy()
predictions = {"glm": pred_glm, "gbm": pred_gbm}

cal_glm = calibration_table(y_true, pred_glm, exposure, n_bins=10)
one_way_age = one_way_table(
    test,
    "driver_age",
    y_true,
    pred_glm,
    exposure,
    n_bins=10,
)
double_lift = double_lift_table(
    y_true,
    pred_glm,
    pred_gbm,
    exposure,
    n_bins=10,
    label_a="glm",
    label_b="gbm",
)
```

## Tables and their contracts

| Function | Grouping | Read it as |
|---|---|---|
| `calibration_table` | Provided groups or exposure-balanced prediction bins | Observed and predicted pure premium, exposure, claim amount, and O/P by segment |
| `one_way_table` | Actual categorical levels; numeric values or exposure-balanced numeric bins | Segment calibration across one feature |
| `double_lift_table` | Exposure-balanced bins of `pred_a / pred_b` | Where two models disagree and which ordering outcomes support |
| `lorenz` | Tied prediction blocks ordered low to high | Cumulative exposure and claim shares plus concentration Gini |

Pass aggregate claim amount as `y_true`, predicted pure-premium rate as
`y_pred`, and exposure as `sample_weight` for these actuarial tables.

## Render every diagnostic

```python
from azoic.plots import (
    model_colors,
    plot_actual_vs_predicted,
    plot_calibration,
    plot_double_lift,
    plot_lift,
    plot_lorenz,
    plot_one_way,
)

colors = model_colors(predictions)

plot_lorenz(
    y_true,
    predictions,
    exposure,
    show_oracle=True,
    path="lorenz.png",
)
plot_lift(
    cal_glm,
    color=colors["glm"],
    label="glm",
    path="lift-glm.png",
)
plot_calibration(
    cal_glm,
    path="calibration-glm.png",
)
plot_one_way(
    one_way_age,
    color=colors["glm"],
    label="glm",
    xlabel="Driver age",
    path="one-way-age.png",
)
plot_double_lift(
    double_lift,
    label_a="glm",
    label_b="gbm",
    color_a=colors["glm"],
    color_b=colors["gbm"],
    path="double-lift.png",
)
plot_actual_vs_predicted(
    y_true,
    pred_glm,
    exposure,
    path="actual-vs-predicted.png",
)
```

Every plot accepts `path=` for direct file output and returns its primary
matplotlib axes. Standalone one-way and double-lift charts add a lower exposure
panel; lift uses exposure bars behind the lines. Visual meaning does not depend
on color: labels, markers, line styles, references, and axes carry the same
distinctions.

## Embed charts in an existing figure

Pass `ax=` when a report owns the layout. `azoic_style` applies the same
defaults to the surrounding figure, and `model_colors` keeps model identity
stable across views.

```python
import matplotlib.pyplot as plt

from azoic.plots import azoic_style, plot_calibration, plot_lorenz

with azoic_style():
    figure, axes = plt.subplots(1, 2, figsize=(12, 5))
    plot_lorenz(y_true, predictions, exposure, ax=axes[0], show_oracle=True)
    plot_calibration(cal_glm, ax=axes[1], title="GLM calibration")
    figure.savefig("diagnostic-grid.png", bbox_inches="tight")
```

For an embedded one-way or double-lift chart, set `exposure="background"` to
show exposure bars inside the supplied axes, or `exposure="none"` to omit them.
`plot_actual_vs_predicted` adds its residual view beside the supplied axes; give
it enough horizontal space.

## Log scales and dense portfolios

- `plot_lift`, `plot_one_way`, and `plot_double_lift` accept `logy=True`.
- `plot_calibration` accepts `logx=True` and `logy=True`.
- `plot_actual_vs_predicted` accepts both log flags, `gridsize`, `bins`, `cmap`,
  and `ax_lim`.
- Use log axes only when the displayed values are positive and multiplicative
  separation matters. Zero-heavy claim outcomes usually need linear axes.
- Actual-versus-predicted uses hexbin density rather than an unreadable cloud;
  with exposure supplied, color intensity represents summed exposure.

## Interpret without over-claiming

!!! warning "Ranking is not calibration"

    Gini and Lorenz measure ordering. O/P, calibration, and one-way views
    measure level. A model needs both kinds of evidence.

- A Lorenz curve that crosses another does not establish dominance.
- Lift should rise with risk while observed and predicted levels stay close.
- Calibration points far from the diagonal indicate segment bias; larger
  exposure points deserve more weight.
- One-way disagreement reveals where bias sits, not automatically why.
- Rising observed double-lift favours model A, falling favours B, and a flat or
  crossing pattern is inconclusive.
- Actual-versus-predicted residual structure can expose tails or heterogeneity,
  but sparse individual losses remain noisy.

[Read the conceptual workflow](actuarial-workflow.md){ .md-button }
[Continue to reporting and operations](operations.md){ .md-button .md-button--primary }
