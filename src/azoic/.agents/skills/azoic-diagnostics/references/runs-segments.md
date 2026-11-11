# Existing runs, segments and stability

Check the installed version and trust provenance before loading pickle. Keep the
matching Python/dependency environment; version validation occurs after unpickling.
Use `load_run(path)` to obtain `(run, estimators)`, then `model_card(run)` or
`comparison_table([run])` for already recorded evidence. Do not call
`run_experiment`, `tune_experiment` or a config-based CLI fit to regenerate a report.

The following uses an existing `predictions.parquet` with aggregate claims,
exposure, rate, `driver_age`, `region` and `period` in aligned rows. These are raw
feature diagnostics; transformed one-ways require the fitted transformation.

```python
import pandas as pd
from azoic import calibration_table, one_way_table, stability_table
from azoic.plots import plot_calibration

predictions = pd.read_parquet("predictions.parquet")
amount, rate, exposure = (predictions[c] for c in ("claim_amount", "rate", "exposure"))
segments = calibration_table(amount, rate, exposure, groups=predictions.region)
one_way = one_way_table(predictions, "driver_age", amount, rate, exposure, n_bins=None)
stability = stability_table(amount, rate, exposure, periods=predictions.period)
ax = plot_calibration(segments)
ax.figure.savefig("calibration.png", bbox_inches="tight")
```

Keep missing groups visible and show exposure/claim totals before interpreting
small segments. Stability uses positive finite rates/exposures, nonmissing periods
and fixed-power deviance; period-relative D² is undefined for a zero-deviance null.
`double_lift_table(amount, rate_a, rate_b, exposure)` groups by their rate ratio;
compare each candidate to observed rates within groups, not just the rise in
observations. Predictions from different records or scales are not comparable.

When rescoring a trusted saved development run, read the original frame in its
saved order and use `df.iloc[list(run.test_indices)]` for development validation.
Verify IDs against `run.record_ids` before using positions; never re-split data.
Predict with `estimators[name].predict(validation[run.feature_names])` and retain
IDs in the output. Saved `report`, `compare` and `predict` CLI routes take `--run`;
none requires refitting. Production `_full` metrics describe training and its
predecessor final metrics describe the earlier frozen fit, not this production fit.
