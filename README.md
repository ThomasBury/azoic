# RiskForge

A scikit-learn-compatible Python toolkit for non-life technical tariff (pure
premium) modelling: actuarial preprocessing, GLM (glum) + GBM (LightGBM),
frequency-severity decomposition, actuarial diagnostics, reproducible runs,
and multiplicative tariff export.

- Full spec and conventions: [`PRD.md`](PRD.md)
- Agent quick rules: [`AGENTS.md`](AGENTS.md)
- Status: [`PROGRESS.md`](PROGRESS.md)

## Install

```bash
uv sync --all-extras        # everything
uv sync                     # core modelling stack only (incl. glum, lightgbm)
```

## Dev

```bash
just check          # ruff + pytest
just test           # pytest -x
just lint
just format
```