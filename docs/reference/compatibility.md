# Compatibility and component composition

!!! note "Unreleased checkout documentation"

    This page describes the current source checkout; some APIs differ from the
    published 0.5.0 package. For a release-compatible journey, start with the
    [first model](../getting-started/first-model.md). See
    [installation](../getting-started/installation.md) for the version boundary.

Use Python composition to supply a frequency or severity estimator. Workflow
`ModelSpec.kind` still supports only its documented GLM, GBM and frequency–severity
construction; arbitrary Python components are not serialized or tuned through YAML.

## Component contract

`FrequencySeverityModel(freq=..., sev=...)` accepts components that support
sklearn cloning, `get_params` and nested `set_params`. Each must accept
`fit(X, y, sample_weight=...)` directly, return itself, accept the supplied
feature DataFrame and categorical representation, and predict one finite value
per row. A component needs neither Azoic inheritance nor a `score` method.
A sklearn pipeline used as a component must itself accept this direct weight
argument; the outer pipeline in the recipe does not need to route weights.

FSM clones the prototypes, leaving them unfitted, and removes exposure, count
and amount columns before calling components. String/object predictors become
pandas categories; declared category order and unused levels are preserved.
Frequency uses count/exposure targets and exposure weights on all rows. Severity
uses amount/count targets and claim-count weights on positive-count rows only.
Frequency predictions are claims per exposure unit, severity predictions are
currency per claim, and their product is pure-premium rate.

Configured portfolio exposure retains the one-day floor. Explicit model weights
must be aligned finite 1D vectors, non-negative and positive in total; individual
zero and sub-day-sized weights are legal. Severity count weights, ranking weights
and diagnostic segment totals remain separate policies.

## Check a component integration

Save the following as `composition.py` and run `python composition.py` in an
environment with Azoic installed. It uses only public imports and no network or
real data. To check a candidate component, replace the appropriate prototype and
adapt the oracle to its documented behavior. This mean-predictor oracle expects
aggregate balance; arbitrary regularized GLMs and GBMs need not satisfy it.

```python
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.dummy import DummyRegressor
from sklearn.model_selection import KFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer

from azoic import FrequencySeverityModel, op_ratio

X = pd.DataFrame({
    "constant": [1.0, 1.0, 1.0],
    "exposure": [1.0, 3.0, 2.0],
    "claim_count": [1, 2, 0],
    "claim_amount": [10.0, 60.0, 0.0],
})
original = X.copy(deep=True)
freq, sev = DummyRegressor(), DummyRegressor()
model = FrequencySeverityModel(freq=freq, sev=sev)
assert model.get_params()["freq__strategy"] == "mean"
model.set_params(freq__strategy="mean", sev__strategy="mean")
assert model.fit(X) is model
assert not hasattr(freq, "constant_") and not hasattr(sev, "constant_")
assert not hasattr(clone(model), "freq_")

# Independent weighted means: frequency = 3/6; severity = 70/3.
np.testing.assert_allclose(model.freq_.predict(X[["constant"]]), 0.5)
np.testing.assert_allclose(model.sev_.predict(X[["constant"]]), 70 / 3)
prediction = model.predict(X[["constant"]])
assert prediction.shape == (3,) and np.isfinite(prediction).all()
np.testing.assert_allclose(prediction, 35 / 3)
np.testing.assert_allclose(np.dot(prediction, X.exposure), 70)
np.testing.assert_allclose(op_ratio(X.claim_amount, prediction, X.exposure), 1)

pipeline = Pipeline([
    ("identity", FunctionTransformer()),
    ("model", clone(model)),
])
assert pipeline.fit(X) is pipeline
np.testing.assert_allclose(pipeline.predict(X), prediction)
repeated = pd.concat([X, X], ignore_index=True)
scores = cross_val_score(
    pipeline, repeated, repeated.claim_amount / repeated.exposure, cv=KFold(2)
)
assert scores.shape == (2,) and np.isfinite(scores).all()
pd.testing.assert_frame_equal(X, original)
```

Both training folds contain severity observations. This cross-validation checks
integration, not generalization. Repository tests also record the exact inputs
received by components and check deliberately broken variants: ignored frequency
weights give `350/27`, ignored severity weights give `10`, aggregate rather than
per-claim severity output gives `35`, and a column-vector component produces an
invalid `(3, 3)` product. FSM currently does not validate component prediction
shapes at runtime; the recipe's shape assertion is essential. Missing cloning
support must fail during cloning/fitting.

Also run sklearn's upstream protocol checks for a general-purpose estimator:

```python
from sklearn.utils.estimator_checks import check_estimator
from azoic import RiskGLM

check_estimator(
    RiskGLM(),
    expected_failed_checks={
        "check_supervised_y_2d": "Azoic rejects column-vector targets; requires strict 1D",
    },
)
```

Retain only that explicit expected failure for Azoic's strict 1D target policy;
do not suppress unrelated failures. FSM needs the targeted DataFrame/outcome
exercise above because general upstream fixtures lack its required columns.
Passing checks establishes only the tested conventions and integration. It does
not establish statistical validity, calibration, absence of leakage or correct
business units in an arbitrary component. See the
[sklearn estimator protocol](https://scikit-learn.org/stable/developers/develop.html).

## Supported public state

The compatibility contract covers root `azoic.__all__` exports and explicitly
documented defining-module imports, constructors, methods and attributes.
Incidental imports and undocumented implementation state carry no promise.
Root and `azoic.workflow` result classes are identical; `Run.config` remains a
runtime-validated `ExperimentConfig`.

- Regressors: documented constructor parameters, `fit`, `predict`, `score`,
  `get_params`, `set_params` and sklearn protocol behavior. Fitted state includes
  `n_features_in_`, `feature_names_in_` when fitted with named columns,
  GLM `backend_`, `coef_`, `intercept_`, GBM `backend_`, and FSM `freq_`, `sev_`.
  Backend access does not extend Azoic's promise to third-party internals.
- Preprocessing: documented fit, transform, feature-name and mapping APIs,
  including `mapping_`, `missing_` and `set_mapping`. Mapping overrides return
  `None`; fitting returns the estimator. Native tree intervals use `<=`, while
  manual/quantile intervals are lower-inclusive. Changed tree mappings require
  an explicit missing destination.
- Results: `Run.config`, `data_fingerprint`, row counts, split indices,
  `feature_names`, `models`, `runtime_versions`, `tuning_settings`, `record_ids`;
  `ModelResult.kind`, `params`, `resolved_params`, `metrics`,
  `calibration_table`, `protected_calibration`. Frozen attributes do not imply
  deep immutability of dictionaries, lists or DataFrames. Experiment/tuning
  return interfaces are unchanged.

No Azoic-specific subclass hooks or internal call order are promised.
`_make_backend`, `_pop_weight`, `_strip_specials` and orchestration helpers stay
internal. Subclass authors maintain the public estimator contract described by
sklearn; inheritance from Azoic is optional.

## Static typing and lazy imports

Root re-exports have static annotations while runtime imports remain lazy.
`fit` returns `Self`; `run_experiment` overloads distinguish `Run` from
`(Run, estimators)` for literal `return_estimators` values. A dynamic boolean
returns their union. Installed artifacts include `py.typed`.

Deliberate dynamic boundaries remain: heterogeneous constructor/configuration,
parameter, tariff and plotting-style dictionaries; pandas formatting values;
third-party FSM component prototypes and backend protocols; reader keyword
arguments forwarded to pandas; and the lazy runtime export lookup. These use
`Any` or heterogeneous dictionaries because their values depend on the selected
backend/component. They do not replace concrete public result and estimator types.
Importing reporting/logging avoids workflow and modelling backends; runtime
`typing.get_type_hints` resolves their `azoic.Run` annotation on demand.

## Azoic 0.x policy and unreleased migration

During `0.y.z`, patch releases preserve this documented contract. Justified
incompatible changes require a minor release and migration notes, without a
mandatory warning period. This is Azoic's policy, stronger than
[SemVer's 0.x baseline](https://semver.org/spec/v2.0.0.html#spec-item-4).
It does not preserve defects or promise undocumented state.

Unreleased M54 change: invalid RiskGBM Tweedie powers and monotonic controls now
raise during `fit`, including values supplied through `set_params`. Constructors
only store parameters so sklearn cloning and parameter search can inspect them.
Move exception handling that surrounded construction to the fitting call. Valid
controls, units and predictions are unchanged. This timing change requires a
minor release under the policy above; M54 does not publish a release.

Unreleased M56 adds column names, invalid-row counts and up to five zero-based
row positions to portfolio outcome, numeric model-weight and missing-time errors.
Validation policies and public function signatures are unchanged. The
[first-model starter](../getting-started/first-model.md) and opening file-based
configuration example are checked against both released 0.5.0 and the checkout;
the in-memory `df=` workflow still requires the checkout.

Unreleased M57 adds `split_portfolio`, `check_experiment` and `azoic check`,
optional ID/excluded-column roles, portfolio-basis metadata and `Run.record_ids`.
Checks require explicit predictors; ordinary fit/tune calls retain feature
inference. Reports label development evidence, and comparison tables add the
`evidence` column (including empty tables). CSV consumers with fixed schemas
must accept this additional column; this schema change requires a minor release.
The released starter remains unchanged. No artifact persistence or final-test
scoring/refitting API is supplied by M57.

Unreleased M58 adds `save_run(run, estimators, path)` and `load_run(path)` in
`azoic.workflow` and the package root. Loading returns the existing
`(Run, estimator_dict)` shape; `Run` and `ModelResult` identities are unchanged.
Artifacts use standard pickle protocol 5, include fitted preprocessing and
estimators, and exclude portfolio frames. Only trusted artifacts with the same
code and environment are supported; recorded version mismatches fail after
unpickling. This is fitted Python state, not a portable deployment format.
See the [saved-candidate recipe](../guide/operations.md#save-fitted-candidates-and-resume-without-training).
`report`, `predict`, `compare --run` and `export-tariff --run` never fit;
config-based operations keep their explicit training behavior. Existing Python
run/tuning return types and defaults remain unchanged. Final-test evaluation and
production refit remain separate work; mapping/factor revisions follow below.

Unreleased M59 adds optional fixed mappings to native transformer constructors,
`RevisedTariff` / `revise_tariff`, and `workflow.revise_run` (also root exports).
Workflow model kinds and ordinary fit/tune return types remain unchanged.
`load_run` can now return revised scoring artifacts alongside native estimators;
`ModelResult.revision` defaults to empty for ordinary/historical constructed
results. Revision snapshots must match their saved candidates. Saved artifacts
require the same source revision; cross-revision pickle compatibility is not
promised. Revised cards/comparison evidence labels distinguish adjusted rates;
revised workbooks add audit columns and export their recorded calibration once.
Fixed groups use typed scalar records and explicit missing/unseen destinations;
fixed bins declare interval closure. See the
[revision recipe](../guide/operations.md#revise-factors-on-a-separate-candidate).
These are technical tariff edits and development evidence; frozen final evaluation
and production refit remain M61 work. Interface/schema changes require a
minor release under the Azoic policy.

Unreleased M60 adds `reporting.tariff_review` (also a lazy root export), returning
the path to a new Markdown/CSV/PNG review bundle. It accepts named Run/estimator
pairs, the original development frame and an ID-aligned incumbent rate table;
mixed contexts are rejected rather than warned about. Ordinary comparison/card
schemas are unchanged. `azoic report --review` adds the same no-fit journey;
plain `report --run` retains its previous behavior. Review CSVs are a new public
schema; incompatible future changes follow the minor-release policy. Bundles
contain IDs/outcomes. This is development review evidence, not final evaluation,
production refit or automated approval. See the
[review contract](../guide/operations.md#prepare-a-tariff-review-with-an-incumbent).

## Final evidence and production artifact boundary

The unreleased `Run` adds `final_evaluation` and `production` records. Final
scoring returns a copied development Run with separate final evidence bound to
its selected fitted state. Production refit returns a new Run with full-training
metrics, no own final evaluation and explicit predecessor lineage. Frozen native
preprocessing remains fitted; only model parameters are refit. Final evaluation
and production refit require recorded unique IDs and original data identities.

`evaluate_final`, `refit_production` and `export_production` are lazy root exports.
All existing workflow model kinds can be evaluated/refit. A three-sheet
production handoff requires an exportable log-link GLM; arbitrary transforms and
GBMs are not silently converted. Bundles use `azoic.production.1` JSON and the
existing trusted same-environment `azoic.run.1` persistence envelope. Fitted
fingerprints are same-environment integrity comparisons, not authentication or
cross-version portability guarantees. Public schema additions and production
metric/evidence names require the planned minor release; 0.5.0 starter blocks
stay unchanged. No deployment API, receiving-engine certification or measured
performance claim is introduced.
