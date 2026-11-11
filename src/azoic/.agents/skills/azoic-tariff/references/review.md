# Review frozen candidates against incumbent technical rates

Check the installed version and artifact trust first. Inputs are saved development
candidates, their exact original development frame, an incumbent frame with the
same unique ID column and annual technical `incumbent_rate`, a new output directory,
and the human's declared selection/rationale. All candidates must share portfolio
basis, fingerprint and development split membership. Different mappings/features
are allowed; mixed populations or currencies are not.

The example reads `selection.json` containing `selected` (such as `revised/glm`,
`original/glm`, `original/gbm` or `incumbent`) and a nonempty `rationale`.
If the user has not selected a candidate, diagnose/compare first and request
the declaration before completing this report; do not invent an approval.

```python
import json
from pathlib import Path

import pandas as pd
from azoic import load_run, tariff_review

selection = json.loads(Path("selection.json").read_text(encoding="utf-8"))
review_path = tariff_review(
    {"original": load_run("candidates.pkl"), "revised": load_run("revised.pkl")},
    df=pd.read_parquet("development.parquet"),
    incumbent=pd.read_parquet("incumbent.parquet"),
    incumbent_rate="incumbent_rate", out="tariff-review",
    selected=selection["selected"], rationale=selection["rationale"],
    segments=["region"],
)
```

This scores frozen rates; it never fits or recalibrates. Retain complete CSVs,
candidate scales and per-record changes. Percentage changes are undefined for
every zero incumbent, including zero-to-zero; do not turn them into zero percent
or silently remove them. Technical pure premium is not commercial premium.
Any target-loss-ratio scenario (for example 70%) is an explicit assumption, not
an estimated result. Review bundles contain IDs/outcomes and require data handling
appropriate to the source portfolio. Human selection is not final-test evidence.
