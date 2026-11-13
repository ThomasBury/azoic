---
name: azoic-tariff
description: Review or revise fitted Azoic tariffs, export workbooks, evaluate frozen selections, or explicitly refit production; keep each operation separately scoped.
metadata:
  azoic-version: "0.6.2"
---

# Azoic tariff

Perform the requested tariff operation. Export does not authorize fitting,
distillation, recalibration, final evaluation or production refitting.

Before using these recipes, run this in the user's project environment:

```python
from importlib.metadata import version
print(version("azoic"))
```

Compare with `metadata.azoic-version` above. If different or absent, report both
versions and treat these recipes as stale guidance. Stop version-specific execution
until matching guidance/environment is available; never silently upgrade dependencies.

Inputs: trusted fitted run/estimators, selected model and requested operation;
original fingerprinted development data for revisions/review, typed factor reasons
for revisions, human selection/rationale and predeclared membership for final
evaluation, exact original full data for production refitting. Ask only for inputs
the requested operation actually needs. Outputs: a distinct reviewed/revised
artifact, faithful workbook, frozen final evidence or production bundle, as requested.

- For factor changes or direct/revised workbook export, read
  [revision-export.md](references/revision-export.md).
- For incumbent/candidate review and human selection, read
  [review.md](references/review.md).
- Only for requested final evaluation, production refitting or production delivery,
  read [final-production.md](references/final-production.md) and execute the relevant
  operation. Finishing one does not authorize the next.

Load pickle only from trusted sources in matching environments. Preserve source
artifacts. Mapping changes require a separately requested new fit with fixed
configuration; post-fit factor revisions do not retrain. Make the recalibration
choice explicit when revising; export revised tariffs with `recalibrate=False`
because their multiplier is already recorded. Reporting/export never silently
fits, distills or recalibrates. A workbook alone cannot replace fitted preprocessing.

Use rate targets/exposure weights when fitting; diagnostic tables take aggregate
claims and predicted rates, sklearn deviances take rates. Distilled GLM fidelity
to a GBM does not establish claims performance. Human selection is a declaration;
final evidence belongs to the selected frozen fit. An explicit full refit creates
new production training evidence and retains predecessor final evidence separately.
Production export is not deployment or receiving-engine validation.
