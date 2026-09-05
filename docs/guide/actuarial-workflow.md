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
5. Refit the selected candidates on outer training data, measure training O/P
   for every candidate, and freeze any training-derived level adjustment before
   inspecting the outer test. Evaluate raw and adjusted candidates on the same
   untouched test rows.
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

Write \(u\) for cumulative exposure share and \(C(u)\) for cumulative claim
share in prediction order. Azoic computes

\[
G=1-2\int_0^1 C(u)\,du=2\int_0^1[u-C(u)]\,du.
\]

This is twice the signed area from the concentration curve to the diagonal,
so it may be negative. A positive Gini does not require the curve to stay
below the diagonal everywhere, and zero Gini does not prove random ranking.
Strictly increasing transformations that preserve ties, including positive
scaling, leave it unchanged and therefore cannot establish premium level.

The pairwise absolute-difference **inequality Gini** measures observed-rate
dispersion independently of model predictions. With rates \(r_i\) and
exposures \(w_i\), it is

\[
G_{\mathrm{ineq}}=
\frac{\sum_i\sum_j w_iw_j|r_i-r_j|}
{2(\sum_i w_i)(\sum_i w_i r_i)}.
\]

It equals concentration Gini when ranking by observed rates. Azoic integrates
tied-score blocks, equivalently the midrank formula; it does not compute
pairwise differences. Its hindsight upper bound generally falls below one.
For rates \([1,3]\) and exposures \([1,2]\), the observed-rate curve passes
through \((1/3,1/7)\), its area is \(17/42\), and Gini is \(4/21\).
Reversing the prediction ordering gives \(-4/21\), while inequality stays
\(4/21\). The [tutorial](fremtpl2.md) executes this example.

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

Measure training O/P for **every** GLM and GBM candidate. Poisson, Gamma, and
Tweedie losses target conditional means; they do not inherently target below
the mean. Restrictions on the model, regularization, finite boosting iterations,
and solver convergence affect achieved calibration. A GLM intercept or a
Poisson GBM objective alone is not a guarantee of total balance.

For observed rate \(r\), predicted rate \(\mu\), and exposure \(w\), our
chain-rule derivation from [glum's deviance and log-link definitions](https://glum.readthedocs.io/en/latest/glm.html)
gives the converged, unpenalized log-link GLM intercept equation

\[
\sum_i w_i(\mu_i-r_i)\mu_i^{1-p}=0.
\]

For Poisson (\(p=1\)), it implies training total balance. For Gamma
(\(p=2\)) and Tweedie (\(1<p<2\)), it generally does not. All three
intercept-only fits recover the weighted mean; adding a varying feature can
break total balance for Gamma and Tweedie even with a converged intercept
score. None of these statements guarantees held-out calibration or balance of
a frequency–severity product. The tutorial includes fitted counterexamples
and a Poisson control with solver tolerances.

If choosing an explicit burn-cost adjustment, calculate each factor as
\(c_m=\sum_{\mathrm{train}}\mathrm{claim\ amount}/\sum_{\mathrm{train}}w\mu_m\)
on the stored training rows and freeze it before inspecting test outcomes.
Multiplying by \(c_m\) balances training totals. It need not improve test
deviance, test O/P, or segment calibration. Show labelled raw and adjusted
holdout results on the same positions; state which predictions feed charts,
scoring, and distillation. The tutorial's charts and scoring use adjusted
rates for every candidate; its distillation teacher and run reports stay raw.

### Visual evidence

| View | Question | Useful signal | Boundary |
|---|---|---|---|
| Lorenz curve | Does the model rank risk? | A curve below the diagonal and non-crossing dominance over a benchmark | Crossing curves do not establish one winner |
| Lift chart | Does observed risk rise with predicted decile, and do levels agree? | Increasing observed lift with observed and predicted lines close together | Wide gaps are calibration errors, not ranking errors |
| Calibration chart | Are segment predictions on level? | Exposure-heavy points near the diagonal | It says nothing about individual-policy accuracy |
| One-way chart | Is a feature segment systematically mispriced? | Observed and predicted lines track across credible levels | Thin-exposure levels are noisy |
| Double-lift chart | Which prediction matches observations within each ratio group? | Smaller observed-minus-predicted gaps in credible groups | Rising observations alone cannot select a model; inspect extreme disagreements |
| Actual vs predicted | Where is policy-level density and residual structure? | Credible grouped mean residuals near zero | The densest band need not be the conditional mean |

In a double-lift view, observed and B rates \([10,20,30]\) against A rates
\([1,20,90]\) give rising A/B ratios, yet B matches all three groups.
The [CAS GLM monograph, section 7.2.2, pp. 78–79](https://www.casact.org/sites/default/files/2021-01/05-Goldburd-Khare-Tevet.pdf#page=88)
compares predictions with observations within ratio groups using normalized
curves. Azoic shows absolute rates, retaining level differences. Extreme ratio
groups contain the largest relative disagreements; assess their exposure and
claims credibility rather than assuming the middle is most informative.

Residuals are \(e=r-\mu\). A constant non-zero conditional mean residual
indicates an additive discrepancy: \(r=\mu+5\) gives \(e=5\), which one
multiplier cannot generally remove. If \(r=c\mu\), then
\(e=(c-1)\mu\); this slope is entirely multiplicative and one factor can
remove it. Inspect credible exposure-weighted grouped means before attributing
remaining curvature to missing structure. Claim-free policies create residuals
near \(-\mu\), so the densest band is not necessarily the mean.

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
