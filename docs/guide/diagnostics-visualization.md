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
| `double_lift_table` | Exposure-balanced bins of `pred_a / pred_b` | How each predicted rate compares with observations within ratio groups |
| `lorenz` | Tied prediction blocks ordered low to high | Cumulative exposure and claim shares plus concentration Gini |
| `stability_table` | Genuine ordered portfolio periods | Exposure, observed and predicted totals, O/P, Gini, deviance, and period-relative \(D^2\) through time |

Pass aggregate claim amount as `y_true`, predicted pure-premium rate as
`y_pred`, and exposure as `sample_weight` for these actuarial tables.

Numeric missing values remain a separate `Missing` segment in `one_way_table`,
including with `n_bins=None`, low-cardinality features, and entirely missing
features. Its exposure, observed claims, and predicted claims contribute to the
portfolio totals; its `level_center` stays undefined. For example, claims of
100, 100, and 10,000 on feature values 20, 40, and missing must total 10,200,
with 10,000 in `Missing`.

Weighted quantiles use only observed grouping values and their corresponding
exposure. Adding a missing value with a large exposure leaves the observed
boundaries unchanged. `plot_one_way` uses labelled positions for every group
when any numeric centre is missing, showing `Missing` in both the rate chart
and the exposure panel or background. Complete numeric tables keep their
natural numeric axis.

## Check stability through real time

Assume `test["period"]` is a real portfolio period carried from the source,
stored as a naturally ordered value such as `pandas.Period`, a datetime, or an
integer year-month. Reuse the same held-out claims, predictions, and exposures
as the other diagnostics:

```python
import numpy as np

from azoic.metrics import stability_table

stability = stability_table(
    y_true,
    pred_glm,
    exposure,
    periods=test["period"].to_numpy(),
)

assert np.isclose(stability["exposure"].sum(), exposure.sum())
assert np.isclose(stability["claim_amount"].sum(), y_true.sum())
assert np.isclose(
    stability["predicted_claim_amount"].sum(),
    np.dot(pred_glm, exposure),
)
```

Each naturally sorted row reports exposure, observed and predicted claim
totals, O/P, concentration Gini, exposure-weighted Tweedie deviance at
`power=1.5`, and \(D^2\) against that period's observed-mean null model. The
function rejects a missing period and checks that exposure, observed claims,
and predicted claims reconcile to the complete input; the assertions keep
that contract visible in a downstream report.

A claim-free period has undefined \(D^2\), reported as `NaN`; its model deviance,
O/P of zero, and calibration totals remain available. A constant positive
observed rate also has undefined \(D^2\) when the null deviance is zero.
Experiment `d2_test` follows the same rule against the test set's observed mean,
with the same fixed Tweedie power of 1.5.

!!! warning "Period means time"

    Do not manufacture periods from row order or substitute an unordered label
    such as region. String labels also sort lexically, so use a semantic period
    or datetime type when chronological order matters. Without a genuine
    ordered period, report non-temporal held-out diagnostics instead.

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

With `show_oracle=True`, the Lorenz reference ranks by observed claim rate
(`y_true / exposure`), retaining aggregate claims and exposure for the cumulative
shares. It is a hindsight ranking bound, unavailable at prediction time, and
its Gini need not be one. Omitted exposures mean unit exposure. Gini is twice
the signed area from the curve to the diagonal; a shaded area is half that
value. The prediction-ordered concentration Gini can be negative. Pairwise
inequality Gini measures observed-rate dispersion; ranking by observed rate
recovers that value. Tied-score blocks are integrated,
equivalently the midrank formula; no pairwise differences are computed.

For `plot_actual_vs_predicted`, `y_true` remains aggregate claim amount.
The function divides it by exposure before drawing both observed values and
residuals, so both axes and the residual calculation use pure-premium rates.

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
- In `plot_actual_vs_predicted`, `logy=True` keeps the prediction y axis
  logarithmic and uses Matplotlib's [symmetric log scale](https://matplotlib.org/stable/gallery/scales/symlog_demo.html)
  for residuals. Negative, zero, and positive errors remain visible, with a
  linear interval from -2 to 2 around zero by default. Callers can adjust
  `linthresh` on the residual axes after plotting; `logy=False` keeps them linear.
- `bins="log"` controls hexbin density colour, independently of either axis.
- Ordinary log axes require positive values. Keep the observed-rate x axis
  linear when the portfolio includes claim-free policies (`logx=False`).
- Actual-versus-predicted rates use hexbin density rather than an unreadable
  cloud; with exposure supplied, color intensity represents summed exposure.

## Interpret without over-claiming

!!! warning "Ranking is not calibration"

    Gini and Lorenz measure ordering. O/P, calibration, and one-way views
    measure level. A model needs both kinds of evidence.

- A Lorenz curve that crosses another does not establish dominance.
- Lift should rise with risk while observed and predicted levels stay close.
- Calibration points far from the diagonal indicate segment bias; larger
  exposure points deserve more weight.
- One-way disagreement reveals where bias sits, not automatically why.
- In double-lift, compare each model with observed rates within each ratio
  group. Direction alone does not identify the better model. Extreme ratio
  groups contain the largest relative disagreements; inspect exposure and
  claims credibility. Curves show absolute rates rather than normalization by
  portfolio averages.
- Read credible exposure-weighted grouped mean residuals before attributing
  remaining curvature to model structure. The densest band in zero-heavy
  outcomes need not be the conditional mean.

### Check double-lift against observations

Observed rates and model B can rise together while A is worse. These repeated
ratios retain three groups through quantile binning:

```python
import numpy as np

from azoic.metrics import double_lift_table

observed = np.repeat([10.0, 20.0, 30.0], 4)
pred_a = np.repeat([1.0, 20.0, 90.0], 4)
example = double_lift_table(observed, pred_a, observed, n_bins=3, label_a="A", label_b="B")
np.testing.assert_allclose(example.mean_ratio, [0.1, 1, 3])
np.testing.assert_allclose(example.observed_pure_premium, [10, 20, 30])
np.testing.assert_allclose(example.B_pure_premium, example.observed_pure_premium)
np.testing.assert_allclose(example.observed_pure_premium - example.A_pure_premium, [9, 0, -60])
```

B matches every group. The [CAS GLM monograph, section 7.2.2](https://www.casact.org/sites/default/files/2021-01/05-Goldburd-Khare-Tevet.pdf#page=88)
uses within-group comparisons of normalized curves; Azoic retains absolute
rate levels. Endpoints are not constrained to match observed rates.

### Separate additive and multiplicative residual errors

Residuals are \(r-\mu\): observed rate minus predicted rate. A constant
non-zero conditional mean residual indicates an additive discrepancy. For
\(r=c\mu\), residuals are \((c-1)\mu\), so a slope can be entirely
multiplicative and removable by one factor.

```python
import numpy as np

from azoic.metrics import op_ratio

mu = np.array([10.0, 20.0, 30.0])
w = np.array([1.0, 2.0, 1.0])
additive = mu + 5
multiplicative = 2 * mu
np.testing.assert_allclose(additive - op_ratio(additive * w, mu, w) * mu, [2.5, 0, -2.5])
np.testing.assert_allclose(multiplicative - op_ratio(multiplicative * w, mu, w) * mu, 0)
```

A single multiplier fixes the multiplicative example but leaves additive errors.
For real outcomes, subtract `predicted_pure_premium` from
`observed_pure_premium` in `calibration_table` to examine grouped mean rate
residuals alongside exposure and claim totals. Those totals help assess
credibility; a density band or a few large claims alone cannot establish bias.

Measure training O/P for every GLM and GBM rather than assuming balance from
the model family. Freeze any burn-cost factor on training rows, then label raw
and adjusted metrics from the same holdout. Positive scaling preserves Gini
but changes level diagnostics; it need not improve holdout or segment fit.
The [tutorial](fremtpl2.md) labels adjusted comparison charts and scoring
separately from raw GLM one-ways at each driver/vehicle age and inside
training-fitted groups. Its distillation teacher stays raw.

[Read the conceptual workflow](actuarial-workflow.md){ .md-button }
[Continue to reporting and operations](operations.md){ .md-button .md-button--primary }
