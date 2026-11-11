# Revise factors or export an existing tariff

Check the installed version first. Load only trusted saved runs in their matching
environment. Use the section for the requested action; exporting an existing
revision does not require running the revision block.

## A requested factor revision

Inputs: `candidates.pkl`, its exact original `development.parquet`, selected `glm`
and approved `replacements.json` (a list of feature, typed level, positive finite
factor and reason records). Example record: `{"feature": "region", "level":
"north", "factor": 1.2, "reason": "Approved pooling after segment review"}`.
Numeric unbinned features use level `"_per_unit"` and a multiplier, not a log
coefficient. Read the fitted factor levels before proposing replacements.

This example makes structural changes with no recalibration. Set
`recalibrate=True` only when training-level recalibration is part of the requested
revision. Its multiplier uses recorded training rows, never validation/final rows.

```python
import json
from pathlib import Path

import pandas as pd
from azoic import load_run, revise_run, save_run

run, estimators = load_run("candidates.pkl")
development = pd.read_parquet("development.parquet")
replacements = json.loads(Path("replacements.json").read_text(encoding="utf-8"))
revised_run, revised_models = revise_run(
    run, estimators, model="glm", df=development,
    replacements=replacements, recalibrate=False,
)
save_run(revised_run, revised_models, "revised.pkl")
```

The source is unchanged. Inspect `revised_run.models["glm"].revision` for original
and replacement factors, reasons and calibration policy. `RevisedTariff` is a
post-fit scoring artifact, not a new model kind. Mapping revisions instead need
a new, explicitly requested fit with fixed bins/groups; never edit the old
pipeline's mapping and assume its coefficients still apply.

## Export an existing fitted or revised GLM

Inputs: the requested saved artifact and output path. This standalone block uses
`revised.pkl`; use `candidates.pkl` for a direct fitted GLM. It deliberately needs
no portfolio or claims, and never fits, distills or recalibrates.

```python
from azoic import export_tariff, load_run

export_run, export_models = load_run("revised.pkl")
export_tariff(export_models["glm"], "tariff.xlsx", recalibrate=False)
```

Predictions of a revised artifact already include its recorded multiplier.
Exporting with recalibration would apply a different scale; keep it off.
Equivalent saved CLI: `azoic export-tariff --run revised.pkl --model glm
--no-recalibrate --out tariff.xlsx`.

Keep fitted preprocessing with the workbook. Native bins/groups, workflow column
removal and passthrough are supported; arbitrary transforms fail before writing.
Do not add an Excel importer or reconstruct a scoring model from display labels.
Workbook application rejects unseen categories and nonfinite numerics. Compare
unrounded workbook rates with Python predictions on declared synthetic cases.

A raw GBM cannot become a multiplicative workbook by export alone. Distillation
is a separate requested fit of a GLM student on a teacher's predictions, using
development training rows. Assess teacher fidelity separately from held-out claims
performance, retain the student pipeline, and do not distill through saved-run
export. Final evaluation and production delivery remain separate actions.
