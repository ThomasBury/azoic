# Actuarial workflow

Profile features, split (temporally when policy-time is available, random
otherwise), compare ranking with Gini and the Lorenz curve, compare adequacy
with the calibration table, O/P ratio and exposure-weighted deviance, and
evaluate the untouched outer test set once.

## Reading the diagnostics

Every diagnostic answers a different question; a verdict needs them all. The
metrics live in `azoic.metrics`; the charts in `azoic.plots`; the API contract
is `metrics.py` returns tables, `plots.py` renders them.

### What each metric tells you

**Gini — ranking only, not accuracy.** A concentration Gini in the actuarial
sense: rank policies by descending predicted pure premium and compute the area
between the cumulative-claims curve and the diagonal. Equal prediction scores
are aggregated into tied blocks before integration, so row order inside a tie
cannot change the result.

The most important consequence is that any monotonic increasing transformation
of the predictions leaves the Gini unchanged — only the rank order matters.

```python
import numpy as np
from azoic.metrics import gini

raw = np.asarray(predictions)
print(f"Gini on rates:      {gini(y_test, raw, exposure):.6f}")
print(f"Gini on exp(rates): {gini(y_test, np.exp(raw), exposure):.6f}")
# Identical to at least six decimals.
```

Two models with the same Gini can charge very different totals. The metric is
diagnostic of ranking, never of pricing level.

**Weighted deviance — the proper score for the response distribution.** Smaller
is better. Use Poisson deviance for frequency, Gamma deviance for severity,
Tweedie deviance (with the right variance power) for pure premium. Azoic
re-exports `sklearn.metrics.mean_{poisson,gamma,tweedie}_deviance`, all of
which accept `sample_weight`. One deviance unit does not translate directly to
euros — when the true distribution differs from the assumed, deviance is a
proxy for accuracy, not a measurement of it.

**$D^2$ — explained-deviance share.** $D^2 = 1 - \text{deviance} / \text{null deviance}$, where
the null model is the exposure-weighted mean. Higher is better. $D^2$ is only
comparable between models of the same response and same family; a frequency
$D^2$ cannot be ranked against a severity $D^2$.

**A/E (actual / expected) $\equiv$ O/P ratio.** $A/E = \sum_i w_i y_i / \sum_i w_i \hat{p}_i$. An O/P
ratio near 1 is necessary but not sufficient: a portfolio can hit 1.0 with
offsetting biases that cancel across segments. Always segment-check.

**Lift by decile.** Each predicted-risk decile's observed pure premium divided
by the portfolio observed pure premium. Bars above 1.0 in the high-predicted-risk
tail expose ranking. The decile range is the rank-quality part; the gap between
observed and predicted is the calibration part.

### What each chart tells you

**Lorenz curve (`plot_lorenz`).** The area between the diagonal and the curve
is the Gini. A curve dominates only when it does not cross another curve;
crossing curves are not a ranking win. Good models bow the curve below the
diagonal; the diagonal itself is random ranking.

**Lift chart (`plot_lift`).** Observed and predicted per segment vs the
portfolio baseline (default 1.0). The two should track on absolute level
(calibration) and the observed should rise with the decile (ranking). Crossing
signals that the model over-estimates in some deciles and under-estimates in
others.

**Calibration chart (`plot_calibration`).** Observed vs predicted pure premium
per segment with the y=x reference. Dispersion around the diagonal is
calibration error; Gini/ranking is read from the Lorenz plot, not this one.

**One-way chart (`plot_one_way`).** Per-feature observed vs predicted pure
premium with exposure-share bars on a secondary axis. The predicted lines should
sit close to the observed line per feature level. A bowed observed line without
a matching predicted line is systematic miscalibration by segment, not bad
ranking. For wide-cardinality numeric features, `one_way_table` exposure-
weight-buckets the column into deciles by default.

**Double-lift chart (`plot_double_lift`).** Orders policies by the A/B ratio
of two predictions and looks at observed rates across ratio deciles. Rising
observed across deciles favours A; falling favours B. Flat, noisy, or crossing
evidence is inconclusive. The middle deciles carry the most diagnostic signal;
the endpoints are anchored by construction (they collect the extreme-ratio
rows).

### What a good model looks like — the five-line checklist

Apply these five tests to a candidate model's diagnostics on the held-out set.
A verdict needs agreement across them.

1. **Accuracy.** Deviance and $D^2$ are smaller / larger than a within-family
   benchmark. Pair Tweedie-deviance with Tweedie-deviance; Poisson with Poisson;
   never cross families.
3. **Portfolio calibration.** A/E near 1, with credible sub-segments checked
   through the one-way charts. A model that hits 1.0 globally but bows every
   one-way is miscalibrated inside the portfolio.
4. **Ranking.** Positive Gini; the Lorenz curve dominates the benchmark without
   crossing; monotonic invariance verified on a re-prediction.
5. **Lift.** Observed per-decile tracks predicted in level; the decile range is
   large; no crossings of observed and predicted.
6. **Business.** Relativities make sense (a younger driver pays more than a
   middle-aged driver; an older vehicle has higher severity); fairness check
   passes; the model is stable when re-fit on a resample.

### The process in a nutshell

Load audited claims with a documented cap, split off an untouched test set,
select every hyperparameter (Tweedie variance power, GLM regularization,
LightGBM grid) on the development split, fit the same protocol on the chosen
model families, produce the final pure-premium estimates, then apply the five
checks above to the same test set and weigh them jointly. No single number
makes a pricing decision; the verdict is the agreement of accuracy,
calibration, ranking, and business constraints.

The [freMTPL2 tutorial](../../tutorial/fremtpl2.html) renders every chart and
table in this page on a public French motor portfolio.