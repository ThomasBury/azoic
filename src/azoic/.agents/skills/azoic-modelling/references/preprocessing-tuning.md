# Conditional modelling choices

Check the installed version first. Use only the section needed by the request.

## Preprocessing

`AutoBinner` and `AutoGrouper` use univariate LightGBM outcomes by default,
with native missing routing. Fit them only on training rows, preferably through
`PreprocessingSpec` inside the workflow. Use `strategy="quantile"` for explicit
unsupervised binning or `strategy="rare"` for explicit rare-level grouping.
Inspect fitted `mapping_`, `missing_` and `unseen_` where applicable.
Learned tree thresholds use `<=`; manual/quantile bins are lower-inclusive.

For approved mappings, configure `fixed` before a new fit. This example is the
`preprocessing` section inside a complete experiment YAML:

```yaml
preprocessing:
  binner:
    cols: [driver_age]
    fixed:
      driver_age: {edges: [30, 60], closure: left, missing: 1}
  grouper:
    cols: [region]
    fixed:
      region:
        groups:
          - {level: north, group: north}
          - {level: south, group: south}
        missing: north
        unseen: south
```

Numeric edges are strictly increasing; declare closure and a zero-based missing
destination. Categorical records preserve scalar types and need explicit missing
and unseen destinations. Fixed features bypass learned credibility/monotonic
guarantees; unlisted features learn on training rows. Do not mutate fitted
mappings and then score old coefficients as if they had been refitted.

## Frequency and severity

Use `ModelSpec(kind="frequency_severity", frequency=..., severity=...)` with
`DatasetSpec.claim_count` declared. Poisson frequency fits count/exposure with
exposure weights; Gamma severity fits amount/count on positive-claim rows with
count weights. `FrequencySeverityModel` applies the filter internally, predicts
their product as a pure-premium rate, and requires any supplied `y` to equal
amount/exposure. Do not replace count weights with exposure weights for severity.

## Tuning, only when requested

Requires the optional `tune` extra already installed in the user's environment.
If unavailable, report the missing extra; do not silently change dependencies.
This block replaces the ordinary fitting call, using the same development-only
`config` and `development` from [development.md](development.md):

```python
from azoic import save_run, tune_experiment

tuned = tune_experiment(config, df=development, n_trials=2,
                        calibration_penalty=1.0, return_estimators=True)
run, estimators = tuned.run, tuned.estimators
save_run(run, estimators, "tuned.pkl")
```

Two trials are a runnable example, not an adequate search recommendation. Agree
the real trial budget and `TuningSpec.search_space` with the modelling task.
The calibration penalty scales `abs(1 - O/P)` against deviance; its usefulness
depends on the portfolio's deviance magnitude. Selection uses an inner split
of outer development training rows, then refits there and evaluates outer
development validation once. Never pass reserved final rows. Tuning
frequency-severity models is unsupported; do not work around it by leaking data.
