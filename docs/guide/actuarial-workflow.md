# Actuarial workflow

Azoic follows one explicit path: understand the portfolio, preserve a final
holdout, fit candidates under the same exposure convention, and judge ranking,
calibration, and business plausibility together.

## The sequence

1. Validate target, exposure, claim-count, feature, and time columns.
2. Profile features and decide which variables to keep, bin, group, or drop.
3. Reserve an untouched temporal test set when an ordered policy-time field
   exists; otherwise use a documented non-temporal holdout.
4. Select preprocessing and model parameters only inside the training data.
5. Refit the selected candidates on the outer training data and evaluate the
   outer test once.
6. Review diagnostics and relativities before reporting or exporting a tariff.

!!! danger "Leakage boundary"

    A final test result is evidence only if outcomes, preprocessing decisions,
    and tuning trials did not influence that partition. Azoic tuning uses an
    inner split of outer training data and evaluates outer test data once.

!!! important "Pure-premium weighting"

    For a rate response, use
    \(y_i = \text{claim amount}_i / \text{exposure}_i\) with exposure as
    `sample_weight`. Use a log-exposure offset only for an aggregate claim
    amount response. Never combine the two formulations.

The special columns travel inside `X` so scikit-learn pipelines and
`GridSearchCV` can route them. Estimators remove those columns before fitting
features.

## Read each diagnostic for its own question

### Ranking

The concentration Gini orders policies from safest to riskiest by predicted
pure premium. Equal scores are aggregated before integration, so row order
inside a tied score cannot change the result. Positive Gini means observed
claims concentrate in the high-predicted-risk tail.

A monotonic transformation of predictions leaves Gini unchanged. It therefore
cannot establish correct premium level.

### Distributional accuracy

Exposure-weighted deviance is a proper score for the assumed response family.
Smaller is better when models use the same response, holdout, and family.
Compare Poisson with Poisson, Gamma with Gamma, and Tweedie with the same
Tweedie power.

Explained deviance is

\[
D^2 = 1 - \frac{\text{candidate deviance}}{\text{null deviance}}.
\]

Higher is better, but \(D^2\) values from different response families are not
comparable.

### Portfolio and segment calibration

The observed/predicted ratio is

\[
\frac{O}{P}
=
\frac{\sum_i \text{claim amount}_i}
     {\sum_i \text{exposure}_i\,\widehat{\text{pure premium}}_i}.
\]

An O/P ratio near 1 is necessary, not sufficient. Opposing segment biases can
cancel at portfolio level, so inspect calibration and one-way tables as well.

### Visual evidence

| View | Question | Useful signal | Boundary |
|---|---|---|---|
| Lorenz curve | Does the model rank risk? | A curve below the diagonal and non-crossing dominance over a benchmark | Crossing curves do not establish one winner |
| Lift chart | Does observed risk rise with predicted decile, and do levels agree? | Increasing observed lift with observed and predicted lines close together | Wide gaps are calibration errors, not ranking errors |
| Calibration chart | Are segment predictions on level? | Exposure-heavy points near the diagonal | It says nothing about individual-policy accuracy |
| One-way chart | Is a feature segment systematically mispriced? | Observed and predicted lines track across credible levels | Thin-exposure levels are noisy |
| Double-lift chart | Where do two models disagree, and which ordering matches outcomes? | A clear observed trend across prediction-ratio deciles | Flat or crossing evidence is inconclusive |
| Actual vs predicted | Where is policy-level density and residual structure? | Dense mass near the reference with residuals around zero | Zero-heavy claims make individual points noisy |

The [diagnostics and visualization guide](diagnostics-visualization.md) contains
the runnable table and plotting recipes.

## Five checks before choosing a model

1. **Accuracy.** Held-out deviance beats a within-family benchmark and
   \(D^2\) improves.
2. **Portfolio calibration.** O/P is credible, and one-way views do not reveal
   material offsetting bias.
3. **Ranking.** Gini is positive and the Lorenz curve improves without relying
   on calibration claims.
4. **Lift.** Observed risk generally rises with predicted risk while observed
   and predicted levels remain close.
5. **Business review.** Relativities are plausible, fairness and governance
   checks pass, and the result is stable enough for its decision.

No single metric makes a pricing decision. The conclusion comes from agreement
between distributional accuracy, ranking, calibration, stability, and business
constraints.

[Profile and preprocess data](data-preprocessing.md){ .md-button .md-button--primary }
[Compare model families](model-choice.md){ .md-button }
[Open the complete tutorial](fremtpl2.md){ .md-button }
