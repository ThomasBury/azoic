# Models and evaluation API

The estimators share the scikit-learn protocol and keep special columns inside
`X`. Metrics calculate actuarial evidence; plot functions render it. Start with
[model choice and fitting](../guide/model-choice.md), then use the
[diagnostics and visualization guide](../guide/diagnostics-visualization.md)
for complete table and chart recipes.

Targets and explicit weights must be finite one-dimensional vectors with one
value per row. Model predictors must keep their fitted names and order;
`predict` and `score` reject renamed, reordered, missing, or extra predictors.
Prediction can omit exposure and frequency–severity outcome columns. Scoring
uses exposure by default; explicit `sample_weight` also works without exposure.
Weights must be non-negative with a positive total, and default exposure weights
must meet the one-day floor.

| Module | Public API | Purpose |
|---|---|---|
| `azoic.models` | `RiskGLM`, `RiskGBM`, `FrequencySeverityModel` | scikit-learn-compatible pure-premium estimators with specials inside `X` |
| `azoic.metrics` | `gini`, `lorenz`, `calibration_table`, `stability_table`, `one_way_table`, `double_lift_table`, `op_ratio`, `mean_tweedie_deviance`, `mean_poisson_deviance`, `mean_gamma_deviance` | Actuarial diagnostics as values and tables |
| `azoic.plots` | `plot_lorenz`, `plot_lift`, `plot_calibration`, `plot_one_way`, `plot_double_lift`, `plot_actual_vs_predicted`, `model_colors`, `azoic_style` | Matplotlib rendering of the metric results |

::: azoic.models

::: azoic.metrics

::: azoic.plots
