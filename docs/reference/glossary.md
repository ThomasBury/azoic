# Glossary

Short definitions of the actuarial and modelling terms used across the guides.
Each entry points to the page that develops it.

| Term | Meaning |
|---|---|
| Pure premium | Expected claim amount per unit of exposure -- the rate every Azoic estimator predicts. See [Actuarial workflow](../guide/actuarial-workflow.md) |
| Exposure | How much risk a row represents (for example policy-years); carried inside `X` and used as `sample_weight`, never as a feature |
| O/P ratio | Observed over predicted portfolio total, \(\sum_i \text{claim amount}_i / \sum_i \text{exposure}_i\,\widehat{\text{pure premium}}_i\); near 1 is necessary, not sufficient |
| Tweedie deviance | Exposure-weighted mean deviance at power \(p\); experiment `deviance_test` fixes \(p = 1.5\) |
| \(D^2\) | \(1 - \text{candidate deviance} / \text{null deviance}\); comparable only within a common response family |
| Gini / Lorenz concentration | Ranking-only metric from the concentration curve, \(G = 1 - 2\int_0^1 C(u)\,du\); never evidence of calibration -- pair with O/P and `calibration_table` |
| Lift | Observed and predicted pure-premium rates by predicted-risk segment; Azoic plots absolute rates without dividing by the portfolio average. See [Diagnostics and visualization](../guide/diagnostics-visualization.md) |
| Double lift | Segments binned by the ratio of two models' predictions, each compared with observations inside the ratio group |
| Calibration | Agreement between observed and predicted totals, portfolio-level (O/P) and per-segment (`calibration_table`) |
| Burn-cost factor \(c_m\) | Training-derived multiplier \(\sum_{\text{train}} \text{claim amount} / \sum_{\text{train}} w\,\mu_m\); balances training totals and is frozen before any test inspection |
| Base, factors, relativities | The multiplicative tariff structure: an intercept base times per-feature level factors, exported to xlsx |
| Frequency--severity | Product of a claim-count rate model (all rows) and a claim-size model (rows with `claim_count > 0` only) |
| PDP / ICE | Partial dependence -- the exposure-weighted average prediction while varying one feature; individual conditional expectation -- one curve per sampled row |
| Distillation | Fitting an exportable log-link GLM student to a positive-objective GBM teacher's predictions |
| Recalibration | Shifting the tariff base to reproduce an observed claim total; CLI export uses training rows only, library callers select their calibration frame and keep evaluation rows separate. See [Reporting and operations](../guide/operations.md) |
| Temporal split | Outer holdout on the latest fraction of `spec.time_col`; equal timestamps never cross the boundary |
| Stability | Per-period diagnostics (exposure, O/P, Gini, deviance, \(D^2\)) through real time via `stability_table` |

[Review the conceptual workflow](../guide/actuarial-workflow.md){ .md-button }
[See the diagnostics contracts](../guide/diagnostics-visualization.md){ .md-button }
