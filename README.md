# Azoic

A scikit-learn-compatible Python toolkit for non-life technical tariff (pure
premium) modelling: actuarial preprocessing, GLM (glum) + GBM (LightGBM),
frequency-severity decomposition, actuarial diagnostics, reproducible runs,
GBM-to-GLM distillation, and multiplicative tariff export.

- Documentation: <https://thomasbury.github.io/azoic/>
- Hosted tutorial series: <https://thomasbury.github.io/azoic/tutorial/index.html>
- Full spec and conventions: [`PRD.md`](PRD.md)
- Agent quick rules: [`AGENTS.md`](AGENTS.md)
- Status: [`PROGRESS.md`](PROGRESS.md)

## Install

Requires Python 3.12 or newer. In your own uv project:

```bash
uv add azoic==0.5.0
uv run azoic --help
```

For a new project, run `uv init --python 3.12 my-pricing-project` and
`cd my-pricing-project` first. The [self-contained starter](docs/getting-started/first-model.md)
compares a direct GLM and raw GBM and exports the fitted GLM using the released
package. No checkout, test fixture or Quarto is required.

The hosted site otherwise documents the unreleased checkout. Features such as
`run_experiment(..., df=...)` are absent from 0.5.0; use the file-based starter
configuration with that release. The checkout still reports version 0.5.0.

The full suite runs on locked Python 3.12 dependencies. Separate installed-package
checks cover low-version Python 3.12 dependencies and Python 3.14 wheels; see
[tested environments](docs/getting-started/installation.md#tested-environments).

For development or the executable tutorial, clone this repository and run:

```bash
uv sync --no-dev                    # runtime only
uv sync                             # default development environment
uv sync --all-extras --all-groups   # everything
```

## Correctness conventions

Frequency models use `claim_count / exposure` with `sample_weight=exposure`.
`deviance_test` is exposure-weighted mean Tweedie deviance with fixed
`power=1.5`. Gini is a concentration Gini for ranking; equal prediction scores
are evaluated as tied blocks.

Temporal holdouts never split equal timestamps. Tuning selects parameters on an
inner split of the outer training partition, then refits on outer training data
and reports development validation. Reserve a separate untouched final-test
portfolio before experimenting; see the [workflow guide](docs/guide/actuarial-workflow.md).
Exported tariffs reject unknown categorical levels and non-finite numeric inputs.

Positive-objective GBMs can be exported through `azoic export-tariff
--distill`; the workbook reproduces the distilled GLM student, not the teacher.

## Executable tutorial series

The numbered Quarto book under [`examples/`](examples/) runs the complete
technical-tariff workflow on pinned OpenML data and then covers tuning,
temporal stability, protected-group audit, and manual tariff recipes. Install
the Jupyter kernel plus the MLflow, Plotly, and tuning extras; install Quarto
separately and ensure its `quarto` executable is on `PATH`.

```bash
uv sync --group demo --extra mlops --extra plot --extra tune
just demo
```

The render produces the ignored book under `examples/_book/`; fetched data,
the tariff workbook, reports, and local MLflow files stay under the ignored
`examples/_artifacts/`. To inspect the recorded run afterward:

```bash
uv run mlflow ui \
  --backend-store-uri sqlite:///examples/_artifacts/fremtpl2/mlflow.db
```

## Dev

Performance measurement commands and the pending practitioner-observation
protocol are in [M62 validation](M62_VALIDATION.md). Benchmark results alone do
not establish user acceptance or deployment readiness.

```bash
just check          # ruff + ty + pytest
just test           # pytest -x
just lint
just format
uv run ty check     # production source types
```
