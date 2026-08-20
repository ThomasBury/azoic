# Azoic

A scikit-learn-compatible Python toolkit for non-life technical tariff (pure
premium) modelling: actuarial preprocessing, GLM (glum) + GBM (LightGBM),
frequency-severity decomposition, actuarial diagnostics, reproducible runs,
GBM-to-GLM distillation, and multiplicative tariff export.

- Full spec and conventions: [`PRD.md`](PRD.md)
- Agent quick rules: [`AGENTS.md`](AGENTS.md)
- Status: [`PROGRESS.md`](PROGRESS.md)

## Install

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
and reports the untouched outer test. Exported tariffs reject unknown categorical
levels and non-finite numeric inputs.

Positive-objective GBMs can be exported through `azoic export-tariff
--distill`; the workbook reproduces the distilled GLM student, not the teacher.

## Executable freMTPL2 tutorial

[`examples/fremtpl2.qmd`](examples/fremtpl2.qmd) runs the complete technical-
tariff workflow on pinned OpenML data. Install its Jupyter kernel plus the
existing MLflow and Plotly extras; install Quarto separately and ensure its
`quarto` executable is on `PATH`.

```bash
uv sync --group demo --extra mlops
just demo
```

The render produces the ignored standalone `examples/fremtpl2.html`; fetched
data, the tariff workbook, reports, and local MLflow files stay under the
ignored `examples/_artifacts/fremtpl2/`. To inspect the recorded run afterward:

```bash
uv run mlflow ui \
  --backend-store-uri sqlite:///examples/_artifacts/fremtpl2/mlflow.db
```

## Dev

```bash
just check          # ruff + ty + pytest
just test           # pytest -x
just lint
just format
uv run ty check     # production source types
```
