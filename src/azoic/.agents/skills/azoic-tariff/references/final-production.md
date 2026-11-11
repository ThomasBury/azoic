# Frozen final evaluation and explicit production handoff

Check installed version and pickle trust first. These are three separately
requested operations. Execute only the section the user authorized; completion
does not imply permission to proceed. All existing model kinds support evaluation
and refitting; the workbook bundle requires an exportable log-link GLM.

## Evaluate the human's frozen selection

Inputs: `selected.pkl`, selected `model` and `rationale` in `selection.json`,
predeclared `portfolio-membership.json` with a `final_test` ID list, and the exact
reserved `final-test.parquet`. Freeze features, factors, calibration and selection
before opening final data. No fitting, tuning, recalibration or candidate search.

```python
import json
from pathlib import Path

import pandas as pd
from azoic import evaluate_final, load_run, save_run

run, estimators = load_run("selected.pkl")
selection = json.loads(Path("selection.json").read_text(encoding="utf-8"))
membership = json.loads(Path("portfolio-membership.json").read_text(encoding="utf-8"))
evaluated = evaluate_final(
    run, estimators, model=selection["model"],
    df=pd.read_parquet("final-test.parquet"),
    final_test_ids=membership["final_test"], rationale=selection["rationale"],
)
save_run(evaluated, estimators, "evaluated.pkl")
```

IDs must match the manifest and be disjoint from development. Evidence belongs
to this frozen fitted state. Do not use final performance to continue selection
and still call it untouched final evidence. API repeat-evaluation guards cannot
prevent reuse through external copies; preserve the procedural boundary.

## Explicitly refit production

Only when requested: supply `evaluated.pkl`, the exact original development and
final frames (including indices/dtypes) and `production-rationale.txt`. No new
hyperparameter search or learned preprocessing. Do not substitute a cleaned or
reconstructed full portfolio for the original fingerprinted rows.

```python
from pathlib import Path

import pandas as pd
from azoic import load_run, refit_production, save_run

evaluated, estimators = load_run("evaluated.pkl")
full = pd.concat([pd.read_parquet("development.parquet"),
                  pd.read_parquet("final-test.parquet")])
production, fitted = refit_production(
    evaluated, estimators, df=full,
    rationale=Path("production-rationale.txt").read_text(encoding="utf-8"),
)
save_run(production, fitted, "production.pkl")
```

Native mappings stay frozen, model parameters are refitted, latest typed factor
overrides are reapplied and the recorded calibration policy is recomputed once on
full training rows. `production.final_evaluation` is empty; `_full` metrics are
training evidence. `production.production` retains predecessor final evidence
separately. Never report the predecessor's score as the new fit's holdout score.

## Deliver the production specification

Only when requested: provide `production.pkl`, caller-authored
`synthetic-cases.parquet` with exactly the selected predictors, and
`feature-units.json` mapping every feature to a nonempty unit. Use synthetic
records, never copied policy rows. Output must be a new versioned directory.

```python
import json
from pathlib import Path

import pandas as pd
from azoic import export_production, load_run

production, fitted = load_run("production.pkl")
specification = export_production(
    production, fitted, cases=pd.read_parquet("synthetic-cases.parquet"),
    feature_units=json.loads(Path("feature-units.json").read_text(encoding="utf-8")),
    out="production-v1",
)
```

This writes the specification, workbook, trusted artifact, scoring recipe and
agreement cases without fitting/recalibration. Run `python production-v1/score.py`
to check supplied unrounded rates/rejections. A receiving engine must separately
implement and validate that contract; export does not demonstrate deployment,
independent engine agreement or practitioner acceptance.
