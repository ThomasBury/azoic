# Reporting, comparison, tuning, MLflow, and tariff operations

!!! note "Unreleased checkout documentation"

    This page describes the current source checkout; some APIs differ from the
    published 0.5.0 package. For a release-compatible journey, start with the
    [first model](../getting-started/first-model.md). See
    [installation](../getting-started/installation.md) for the version boundary.

Once candidates have a valid outer-test result, Azoic reuses the same `Run` for
human-readable reports, comparison, optional experiment tracking, and tariff
export.

## Write model cards and comparisons

```python
from pathlib import Path

from azoic.reporting import comparison_dashboard, comparison_table, model_card

Path("model-card.md").write_text(model_card(run), encoding="utf-8")

comparison = comparison_table([baseline_run, candidate_run])
comparison.to_csv("comparison.csv", index=False)
Path("comparison.html").write_text(
    comparison_dashboard([baseline_run, candidate_run]),
    encoding="utf-8",
)
```

## Save fitted candidates and resume without training

Keep a fitted candidate to review or score it later. The following checkout APIs
save the existing `Run` and every fitted estimator, including learned bin/group
mappings, as one standard Python pickle file:

```python
from azoic import load_run, run_experiment, save_run

run, estimators = run_experiment(config, return_estimators=True)
save_run(run, estimators, "candidates.pkl")

restored_run, fitted = load_run("candidates.pkl")
rates = fitted["tweedie-glm"].predict(new_portfolio[restored_run.feature_names])
```

Use the estimator dictionary returned alongside that same run. Reloading does
not read `config.data_path`, fit models or relearn mappings. Python prediction
returns pure-premium rates; multiply by exposure only when period costs are
needed. Preserve predictor names, order, types and category representation.

The file includes config, versions, data fingerprint, split positions, recorded
IDs and aggregate diagnostics. Portfolio row frames are excluded; retain them
separately for audit and export recalibration. IDs, category vocabulary, model
state and aggregate claims remain sensitive information. New files use temporary
file permissions (user-only on POSIX); replacements preserve permission bits.
A failed serialization or replacement preserves the previous artifact.

!!! warning "Trusted files and matching environments only"

    Pickle loading can execute code. Only load files whose source and integrity
    you trust. Keep the same Azoic source revision and Python/dependency lock;
    `load_run` rejects differing recorded runtime versions after unpickling.
    This check does not authenticate the file or make untrusted loading safe.
    Cross-version portability and arbitrary custom Python components are not
    supported. See scikit-learn's
    [persistence guidance](https://scikit-learn.org/stable/model_persistence.html).

The CLI can save ordinary or selected tuned candidates, then consume their
stored state without training:

```bash
azoic fit --config experiment.yaml --save-run candidates.pkl --quiet
azoic tune --config experiment.yaml --save-run tuned.pkl --best-config selected.yaml --quiet
azoic compare --run candidates.pkl --run tuned.pkl --out comparison.csv
azoic report --run tuned.pkl --out model-card.md
azoic predict --run tuned.pkl --model tweedie-glm --data predictors.parquet --out rates.csv
azoic export-tariff --run tuned.pkl --model tweedie-glm --no-recalibrate --out structural.xlsx
azoic export-tariff --run tuned.pkl --model tweedie-glm --data development.parquet --out tariff.xlsx
```

`predictors.parquet` needs the saved predictors and, if declared, unique record
IDs; outcomes and exposure are unnecessary for rate scoring. The CSV preserves
input order and contains `predicted_rate` plus the declared ID. Reporting and
comparison reuse saved development diagnostics; scoring does not evaluate
final-test outcomes or establish independent performance.

Saved-run GLM recalibration requires the full original development frame,
including its index, row order, dtypes and categorical metadata. Its fingerprint
must match before the stored training positions are used. `--no-recalibrate`
exports structural fitted rates without any data file. Saved-run export never
fits or distills: GBM distillation remains an explicit `--config --distill`
training operation.

The selected config is also inside `tuned.pkl`; `--best-config` writes a separate
YAML with an absolute local data path so relocating that YAML does not change
its source data. Running it trains a new candidate. `fit`, `tune`, positional
`compare` configs and `export-tariff --config` remain training operations;
`compare` rejects mixing positional configs and saved runs. Controlled revisions
are described below; final evaluation and production refit remain M61 work.

## Interpret saved development evidence

A model card is Markdown and records the experiment data contract, fingerprint,
split, features, model parameters, held-out metrics, and a calibration preview
(first 12 rows; write full tables separately when every segment is needed).

Workflow runs snapshot the configuration and nested model parameters, so later
changes to the caller's config do not rewrite a result. Each model's
`resolved_params` also records every actual wrapper and preprocessing constructor
setting, including defaults, with a qualified `class` and sklearn
`__` component paths (for example `model__alpha` or `model__sev__family`).
Estimator and function values become qualified names; containers are copied.
This records constructors, not fitted coefficients, learned mappings or hidden
backend defaults.

`run.runtime_versions` records Python, Azoic and its numerical/model/data/runtime
stack once after the final fit. Tuned runs add Optuna and `run.tuning_settings`:
effective trial count, calibration penalty, search seed, sequential execution,
inner split controls and each model's sampler class, seed and resolved search
space. Keyword overrides take precedence over YAML; sampler seed is the search
seed plus the model's insertion position. Model seeds remain in `resolved_params`
and may be `None`. An ordinary run has empty tuning settings even if its config
contains a tuning section.

Cards show versions, tuning controls and constructor identities compactly;
inspect the result containers for all settings. MLflow uses `runtime_versions.*`,
`tuning_settings.*` and `<model>.resolved_params.*`, separately from existing
explicit `<model>.params.*`. Historical/manual results default to empty provenance:
cards say **unrecorded**, and logging never substitutes today's environment.

These snapshots support audit, not portable replay or deterministic predictions.
Keep the input data and environment lock yourself; `save_run` retains the fitted
models with their Run. Public
dictionaries and DataFrames remain mutable. The fingerprint includes categorical
vocabulary
(even unused levels), its dtype, declared category order, and the ordered flag.
Category-aware fingerprints intentionally change; evaluate older runs again
before comparing them with fresh results.

Comparison tables and dashboards warn once when runs differ in dataset
fingerprint, target/exposure columns, declared portfolio basis, or holdout
membership. The warning names the affected runs and preserves every row for descriptive comparison. Different
orders of the same holdout positions count as the same evaluated sample.

The CLI can run several configs and write their comparison table:

```bash
azoic compare baseline.yaml candidate.yaml --out comparison.csv
```

The Python-only `comparison_dashboard` API returns a standalone HTML string with
Plotly JavaScript embedded and requires the `plot` extra; the CSV table does
not. Write the string to a file as above and open it in a browser. There is no
dashboard CLI command.

All comparisons here are **development evidence**. Reserve a separate
[final-test portfolio](actuarial-workflow.md#freeze-portfolio-membership-before-experimenting)
before experimenting. The `test` metric suffix denotes development validation;
repeated review can influence selection, so it cannot establish independent
final-test performance.

## Tune without touching development validation during search

```bash
uv add "azoic[tune]"
azoic tune --config experiment.yaml
```

Put optional trial settings and model-specific scalar distributions in the
experiment YAML:

```yaml
tuning:
  n_trials: 30
  calibration_penalty: 2.0
  search_space:
    tweedie-glm:
      alpha:
        type: float
        low: 1.0e-6
        high: 0.1
        log: true
      l1_ratio:
        type: float
        low: 0.0
        high: 1.0
    tweedie-gbm:
      num_leaves:
        type: int
        low: 8
        high: 64
        step: 8
      max_depth:
        type: categorical
        choices: [-1, 4, 6]
```

A custom entry replaces that model's built-in search space; it is not merged
with the defaults. A model without a custom entry keeps the existing GLM or GBM
space exactly. `--trials` and `--calibration-penalty` override YAML values.
Omitted flags defer to YAML, then to the legacy defaults of 20 trials and 1.0.

`tune_experiment` still creates an inner split of outer training data,
minimizes Tweedie deviance plus a numeric O/P penalty, refits selected
parameters on all outer training data, and evaluates outer test once.
Configuration changes the candidate values, not this leakage boundary.

Invalid bounds, non-finite values, incompatible `step` and `log` settings,
empty spaces or categorical choices, unknown models or estimator parameters,
and extra fields fail while parsing the config. Family, link, objective,
Tweedie powers, exposure routing, and random seeds cannot be tuned.
Frequency-severity tuning remains unsupported.

!!! warning "Scale the calibration penalty"

    `abs(1 - O/P)` is unitless while Tweedie deviance depends on the portfolio.
    Increase the penalty only when calibration loss is too small to affect trial
    ordering; do not tune it on the final test result.

## Prepare a tariff review with an incumbent

This unreleased checkout API writes a self-contained development review: a
Markdown decision record, full CSV evidence and the existing lift/one-way plots.
It scores fitted candidates without fitting or recalibrating them. Keep final-test
data reserved for the later frozen evaluation; repeated development validation
cannot establish independent superiority.

Use the original development frame in its saved order. Every run must record
`spec.id_col`, the same IDs, fingerprint, portfolio basis and training/validation
membership. Different predictors, fixed mappings and fitted factors are allowed.
The incumbent table must contain that same ID column and exactly those unique,
nonmissing IDs, in any order. Supply **technical pure-premium rates per year** on
the same currency/claim basis, with commercial loadings removed upstream.
Missing/duplicate/extra IDs and invalid rates raise before writing a bundle.

```python
import pandas as pd
from azoic import load_run, tariff_review

# These artifacts were fitted/revised beforehand; loading never fits.
fitted = load_run("fitted.pkl")
recalibrated = load_run("recalibrated.pkl")
revised = load_run("revised.pkl")

report = tariff_review(
    {"fitted": fitted, "recalibrated": recalibrated, "revised": revised},
    df=pd.read_parquet("development.parquet"),
    incumbent=pd.read_parquet("incumbent.parquet"),  # ID plus technical_rate
    incumbent_rate="technical_rate",
    out="tariff-review-01",  # new directory; its parent must exist
    selected="revised/tweedie-glm",
    rationale="Retain the reviewed age mapping and documented factor changes. "
              "Training level reconciles; review validation segments before approval.",
    limitations=["Sparse segments remain uncertain; independent final evaluation is pending."],
    segments=["driver_age", "region"],
)
print(report)  # tariff-review-01/review.md
```

Candidate labels are `alias/model`; `selected` may also be `incumbent`. The
selection and rationale are the author's declaration, not an automatic approval.
To create a recalibrated candidate beforehand, call `revise_run` with
`replacements=[]` and `recalibrate=True`, using its recorded training population
as in the [revision recipe](#revise-factors-on-a-separate-candidate). Save that
returned pair separately. Report scales distinguish raw fitted, recalibrated,
revised and structural revised predictions; the recorded multiplier is never
applied twice. A new mapping is a separate refit, not a report-time edit.

The equivalent saved-run command uses each file's unique stem as its alias:

```bash
azoic report --review --run fitted.pkl --run recalibrated.pkl --run revised.pkl \
  --data development.parquet --incumbent incumbent.parquet \
  --incumbent-rate technical_rate --selected revised/tweedie-glm \
  --rationale "Reviewed age mapping and factor changes; final evaluation pending." \
  --segment driver_age --segment region --out tariff-review-01
```

Without `--review`, `azoic report --run fitted.pkl` retains the compact model card
and needs no data. Review directories must be new: an existing directory is
rejected, and CSV/plot failures leave no partial bundle. Keep the bundle with
its saved artifacts and environment; it contains record IDs and outcomes.

| CSV | Complete evidence |
|---|---|
| `candidates.csv` | Candidate scale, recorded multiplier, config, runtime/tuning and revision evidence; factor availability |
| `records.csv` | Identical IDs/order and split for every rate, ID types, exposure/outcomes, annual rate, period cost and incumbent change |
| `totals.csv` | Whole development, training and validation totals, available counts, changed rows/exposure, O/P, Gini and fixed-power Tweedie deviance/D² |
| `calibration.csv` | Validation risk-decile calibration, exposure and available counts |
| `segments.csv` | Raw segment levels on identical rows, totals, available counts, changed records and aggregate incumbent changes |
| `temporal.csv` | Period totals, available counts and diagnostics within each partition; empty when no `time_col` is declared |
| `rate_changes.csv` | Percentage-change bands, unchanged rows and explicitly undefined zero-incumbent cases, with counts/exposure and costs |
| `mappings.csv`, `mapping_changes.csv` | Native preprocessing snapshots and before/after changes relative to the first candidate |
| `factors.csv`, `factor_changes.csv`, `revision_history.csv` | Complete log-link GLM factors/base, changes relative to the first candidate, and recorded replacement reasons |

Markdown previews stop at twelve rows; CSVs retain every row and unrounded
rates. Review the linked full tables before choosing a tariff. Empty cells mean
undefined or unavailable values: percentage change is undefined for **every zero
incumbent**, including zero-to-zero. Absolute differences remain defined.
Nonpositive predictions give infinite fixed-power deviance and undefined D²;
zero predicted totals give undefined O/P. Claim-free groups can have undefined D².
These are exposed, not replaced with favorable scores.

Segments default to the first run's raw predictors; protected columns are always
included. Raw numeric values can produce large tables; pass a short explicit
`segments` list for focused reviews. Groups stay identical across candidates;
they are not each model's learned bins. Missing raw levels retain their totals.
The report shows lift plots for every candidate and one-way plots for the selected
candidate. GBM/FSM candidates retain metrics and rate comparisons but have no
multiplicative factor decomposition. Temporal tables are descriptive when the
underlying split is random. Change bands are descriptive, not universal approval
thresholds, and no superiority claim follows from this report alone.

## Log a completed run to MLflow

```python
from azoic.mlops import log_run

run_id = log_run(
    run,
    tracking_uri="sqlite:///mlflow.db",
    experiment_name="motor-pricing",
    artifacts=["model-card.md", "comparison.csv"],
)
print(run_id)
```

Install `azoic[mlops]` first. `log_run` records the data fingerprint,
flattened `experiment.preprocessing.binner.*` / `grouper.*` settings, each
model's `preprocess` flag, experiment fields, model parameters, finite metrics,
and the requested files or directories. The run name defaults to the experiment
config name. Artifacts
upload under `artifact_path="artifacts"` by default; a directory's contents
nest under `artifacts/<dir_name>` so the directory name is preserved, and a
missing artifact path raises `FileNotFoundError`. NaN and infinite metrics are
skipped because MLflow rejects non-finite values. Remote tracking remains an
environment concern; Azoic does not invent credentials or deployment policy.

## Export a multiplicative tariff

### Revise factors on a separate candidate

Use `revise_run` after any mapping change has been fitted through a new config.
It changes factors without fitting, verifies the original development portfolio
fingerprint and row order, and uses the recorded training positions for optional
recalibration. Every replacement requires a positive finite factor and a reason.
The `level` must match the fitted category's scalar type; numeric features use
`"_per_unit"` and a per-unit multiplier, not a log coefficient.

```python
from azoic import export_tariff, revise_run, save_run
from azoic.reporting import model_card

revised_run, revised_models = revise_run(
    run,
    estimators,
    model="tweedie-glm",
    df=development,
    replacements=[
        {
            "feature": "region",
            "level": "metro",
            "factor": 1.2,
            "reason": "Approved technical adjustment after segment review",
        }
    ],
)
revised = revised_models["tweedie-glm"]
revised_rates = revised.predict(new_portfolio[revised_run.feature_names])
print(model_card(revised_run))
save_run(revised_run, revised_models, "revised.pkl")
export_tariff(revised, "revised.xlsx", recalibrate=False)
```

`RevisedTariff` is a scoring artifact, not an estimator to fit or tune. It holds
a copy of its fitted source, revised factors and audit evidence. The original
Run/model remain unchanged. The returned Run recomputes development diagnostics
from revised predictions; cards and comparisons label the revision. Inspect
`revised_run.models["tweedie-glm"].revision` for each original/replacement factor,
reason and the calibration population, totals and multiplier. Public containers
remain caller-mutable; revise through the factory to keep the evidence aligned.

Recalibration defaults to on and computes one multiplier from the revised
training predictions. It multiplies the base once; predictions already include
it. Zero observed training claims give a zero multiplier. Repeated revisions
retain factor-change history and recompute calibration from the uncalibrated
revised tariff, rather than multiplying the previous calibration again. Set
`recalibrate=False` on `revise_run` for structural revised rates. A changed
reference-category factor is retained explicitly; the original reference basis
is not renormalized.

Export a revision with `recalibrate=False` because its calibration policy is
already recorded. The three-sheet writer includes preprocessing mappings,
original factors/reasons and the recorded multiplier. It preserves the existing
workbook on failed writes. The saved CLI route follows the same rule:

```bash
azoic report --run revised.pkl --out revised-card.md
azoic predict --run revised.pkl --model tweedie-glm --data predictors.parquet --out revised-rates.csv
azoic export-tariff --run revised.pkl --model tweedie-glm --no-recalibrate --out revised.xlsx
```

The lower-level `revise_tariff` API returns the same artifact for a direct GLM
or supported pipeline. Its caller chooses the calibration population explicitly;
`revise_run` adds saved membership checks, refreshed diagnostics and persistence
evidence. GBM/FSM factor revision is unsupported: use an explicit fitted GLM
tariff. Senior review and independent final evaluation remain later phases.

### Export a fitted GLM

A fitted log-link `RiskGLM` or pipeline ending in one can be written to a
three-sheet workbook:

```bash
azoic export-tariff \
  --config experiment.yaml \
  --model tweedie-glm \
  --out tariff.xlsx
```

| Sheet | Contents |
|---|---|
| `base_rate` | Multiplicative base, family, resolved link, intercept, and recalibration metadata |
| `factors` | Numeric per-unit factors and categorical level relativities |
| `mappings` | Feature roles, levels, references, and fitted bin/group mappings |

Pipeline export supports native `AutoBinner` and `AutoGrouper` steps, the
workflow's column removal, and `None` / `"passthrough"` steps. Preprocessing
mapping rows follow pipeline order; removed columns have role `dropped`.
Scalers, arbitrary function transforms, `ColumnTransformer`, nested pipelines
and custom transformer subclasses are rejected before a workbook is opened.
Earlier exports could silently omit these transforms and misdescribe the fitted
model. Keep those pipelines in Python for scoring, or use the supported
preprocessing when a workbook is required.

Export writes and closes a temporary workbook beside the destination, then
atomically replaces the destination. A serialization, save or replacement error
preserves an existing workbook and removes the temporary file. Existing
destination permission bits are copied before replacement; a permission-setting
error also preserves the original file. This protects against failed writes;
it is not a power-loss durability guarantee.

Application sums the linear predictor before exponentiating. Invalid or
unrepresentable factors and rates raise `ValueError`; export also rejects
unrepresentable numeric per-unit factors. Zero observed claims can recalibrate
the base to zero. Workbook labels are literal text, including `=1+1`; numeric
and boolean level labels keep their types.

Recalibration is on by default and shifts the base to reproduce the observed
claim amount on `Run.train_indices` only. Direct GLMs and distilled students
keep the existing fit and holdout; the CLI does not refit on the full frame.
Holdout outcomes cannot change the exported rates or calibration factor.

Use `--no-recalibrate` when the structural model total is required. The tutorial
exports with `recalibrate=False` plus training-frame metadata and reports a
separate external training multiplier. Library `export_tariff` callers choose
their calibration frame explicitly and must supply a finite, non-negative 1D
vector of aggregate claim amounts with one value per calibration row. Keep
evaluation rows separate from that frame.

A positive-objective GBM is not itself a multiplicative table. Distill a
held-out GLM student explicitly:

```bash
azoic export-tariff \
  --config experiment.yaml \
  --model tweedie-gbm \
  --distill \
  --out distilled-tariff.xlsx
```

The workbook describes the student and includes held-out teacher/student
fidelity metadata. The student is a log-link `RiskGLM` that inherits the
teacher's objective as its family -- and the Tweedie power when the objective
is tweedie -- fits with the `RiskGLM` default `alpha=0.001`, and reuses a copy
of the teacher's already-fitted preprocessing, so bins and group mappings are
not relearned from the holdout. Teacher predictions and exposure must be
positive and finite on both the fit and validation frames. Fidelity measures
agreement with teacher predictions, not accuracy against claims. The CLI uses
the run's stored training and test positions. Direct `distill_gbm` callers must
supply disjoint observations: the object-identity guard rejects the same frame
object, but separate objects or copies do not prove row independence. The
Python distillation API also preserves generic fitted upstream transforms;
exporting its student still requires the supported preprocessing above. The
[freMTPL2 tutorial](fremtpl2.md) applies the workbook
after fitted preprocessing and compares it with the direct GLM, raw GBM, and
structured teacher on the same held-out claims. It exports with
`recalibrate=False` and training-frame feature metadata, then reports raw metrics
and a separate external multiplier based on each candidate's own training O/P,
including the applied workbook. Calibration, Lorenz, and common training-bin age
comparisons accompany deviance, D², Gini, O/P, and portfolio totals.

!!! danger "Application boundary"

    Tariff application rejects unseen categorical levels and non-finite numeric
    inputs. Do not silently map an unknown quote-time category into a factor.
    Resolve the data contract or publish an explicitly approved mapping first.

## Score an outcome-free frame

Fitted workflow pipelines do not need outcome columns at prediction time.
Select exactly the fitted predictors, in order, followed by the configured
exposure column. Keep policy identifiers and other metadata alongside the
output, outside the prediction inputs:

```python
from azoic.workflow import run_experiment

run, estimators = run_experiment(config, return_estimators=True)
pipeline = estimators["tweedie-glm"]

unlabeled = test[[*run.feature_names, config.spec.exposure]]
predictions = pipeline.predict(unlabeled)
scored = test[["policy_id"]].copy()
scored["predicted_rate"] = predictions
scored["expected_period_cost"] = predictions * test[config.spec.exposure].to_numpy()
```

Here `test` is your scoring DataFrame and `policy_id` is its identifier column;
substitute your identifier name. Merely dropping outcomes can leave unused
columns that the fitted estimator rejects.

When the config declares preprocessing, the fitted binner and grouper accept
outcome-free or feature-only frames at prediction time, and a `drop_specials`
step removes any present outcome columns before the final estimator so targets
never leak into prediction inputs. Frequency-severity pipelines strip the same
columns inside the meta-estimator instead.

## Freeze final evidence, then refit production explicitly

Finish development review and record the selected candidate and rationale before
opening the reserved final-test portfolio. Keep the
[original membership manifest](actuarial-workflow.md#freeze-portfolio-membership-before-experimenting)
and the same target, exposure and claim valuation basis. Evaluation scores the
existing fitted candidate: it does not fit, tune, revise factors or recalibrate.

```python
import json
from pathlib import Path

import pandas as pd
from azoic import evaluate_final, export_production, load_run, refit_production, save_run

run, estimators = load_run("selected.pkl")
manifest = json.loads(Path("portfolio-membership.json").read_text())
final_test = pd.read_parquet("final-test.parquet")
evaluated = evaluate_final(
    run, estimators, model="glm", df=final_test,
    final_test_ids=manifest["final_test"],
    rationale="Selected after development tariff review and recorded approval",
)
save_run(evaluated, estimators, "evaluated.pkl")

# This is a separate, explicit fitting operation on the original full portfolio.
full = pd.concat([pd.read_parquet("development.parquet"), final_test])
full.to_parquet("full-production.parquet")
production, fitted = refit_production(
    evaluated, estimators, df=full,
    rationale="Approved parameter refit on development plus the final-test portfolio",
)
save_run(production, fitted, "production.pkl")

# Author synthetic cases; never copy real policy rows into the handoff cases.
cases = pd.DataFrame({"driver_age": [25.0, 60.0], "region": ["north", "south"]})
export_production(
    production, fitted, cases=cases,
    feature_units={"driver_age": "years", "region": "category"},
    out="production-handoff",
)
```

Adapt the selected model, predictor names, synthetic levels and units to the
actual saved run. The example assumes those two predictors. All existing model
kinds support final evaluation and refit. The workbook handoff requires a
log-link GLM with supported native preprocessing; it never distills a GBM.
An external calibration multiplier is not an artifact: record it beforehand with
`revise_run(..., replacements=[], recalibrate=True)` if that is the approved
candidate. A handoff never silently recalibrates a second time.

Final IDs must be unique, match the supplied manifest exactly and be disjoint
from every development ID. The returned copied `Run.final_evaluation` binds the
selected fitted-state/configuration fingerprints, final-data fingerprint, IDs, metrics,
calibration totals and selection rationale. Development metrics stay separate.
The original run remains unchanged. An already evaluated run cannot be evaluated
again through this API. A caller can still reuse an older copy or inspect data
outside Azoic; predeclaration and one-time final use remain procedural controls.

`refit_production` requires that evaluated candidate and exactly the union of
its development and final-test membership. It verifies both original frames'
values, column order, dtypes and indices. Concatenate the exact saved
development/final frames as above and retain their indices when writing the full
Parquet; an earlier raw source file may lack the declared IDs/partition metadata.
The full frame may be reordered. Refitting freezes learned native
bins/groups, including interval closure and missing/unseen destinations, and
clones only the final estimator's settings to fit new parameters. It never
searches hyperparameters or relearns transformations. Recorded factor overrides
are reapplied (the latest approved replacement per typed level); the recorded
calibration policy is recomputed once on the full training portfolio.

The new `Run.production` records rationale, identities, mapping/calibration
policy, full-population rate-change summaries and predecessor evaluation.
`Run.final_evaluation` is empty for this new fit. Its metrics end in `_full` and
are training evidence only; predecessor holdout metrics do not become claims
about the new fit. `model_card` and `comparison_table` label this distinction.
Use the table for production comparisons; the development dashboard and tariff
review reject production artifacts. Revisions must precede final evaluation.

The CLI consumes those same saved artifacts and JSON declarations:

```bash
azoic evaluate-final --run selected.pkl --model glm --data final-test.parquet \
  --membership portfolio-membership.json --rationale "Frozen selection" --out evaluated.pkl
azoic refit-production --run evaluated.pkl --data full-production.parquet \
  --rationale "Approved full fit" --out production.pkl
azoic export-production --run production.pkl --cases synthetic-cases.parquet \
  --units feature-units.json --out production-handoff
python production-handoff/score.py
python production-handoff/score.py predictors.parquet rates.csv
```

`feature-units.json` maps every predictor to a nonempty unit string, for example
`{"driver_age": "years", "region": "category"}`. `synthetic-cases.parquet` has
exactly the selected predictor columns. Missing files, invalid inputs and failed
writes produce CLI parameter errors. CLI evaluation/refit require a new saved
output path; the Python `save_run` replacement policy remains unchanged.

The new handoff directory contains:

| File | Contract |
| --- | --- |
| `specification.json` | `azoic.production.1`: predictor types/declared units, portfolio basis, ordered typed mappings, exact edges/closure/routes, base/factors/formula, calibration, revisions, artifact hashes, runtime/settings and evaluation/refit lineage |
| `tariff.xlsx` | Existing `base_rate`, `factors`, `mappings` sheets; rates match the fitted artifact without further calibration |
| `production.pkl` | Trusted same-environment production Run and fitted model; source row frames are excluded |
| `agreement.json` | Caller synthetic cases plus exact/neighboring boundaries, known levels, missing/unseen inputs and nonfinite numeric probes; expected unrounded rate or explicit rejection |
| `score.py` | With no arguments, verifies agreement cases; with input Parquet/output CSV arguments, batch scores rates and optional exposure-period costs |

JSON uses `{"$float": "inf"}`, `-inf` or `nan` for nonfinite values; `null` is
missing. Category levels remain typed scalar records. Agreement uses relative
tolerance `1e-12` and absolute tolerance zero; rates are never rounded. Period
cost is rate times exposure in years. The recipe preserves input order and
available IDs. An existing handoff directory is rejected; failed writes remove
staging and preserve earlier bundles. The specification and saved run include
real membership IDs and aggregate outcomes; apply portfolio data controls even
though agreement inputs are synthetic.

The receiving engine must implement these mappings and pass the same cases.
Passing Azoic's Python checks does not establish agreement with an external
engine. Technical pure premium excludes commercial loadings, taxes and discounts.
Release, deployment, monitoring and rollback ownership remain downstream.
Performance measurements and observed user handoffs remain M62 work.

## Operational checklist

- Preserve the config, data fingerprint, and generated report together.
- Compare candidates on the same held-out rows.
- Record optional integrations without moving business logic into them.
- Check workbook totals and reference levels before deployment.
- Score an outcome-free frame to prove target and claim-count columns are not
  required at prediction time.
- Treat tariff deployment, approvals, monitoring, and rollback as downstream
  controls, not assumptions hidden inside a modelling library.

[Review configuration and CLI details](../reference/configuration-cli.md){ .md-button }
[Open the freMTPL2 operations example](fremtpl2.md){ .md-button .md-button--primary }
