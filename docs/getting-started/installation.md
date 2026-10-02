# Installation

Azoic requires Python 3.12 or newer and pandas 3.0 or newer. pandas 2 is no
longer supported. Use a virtual environment so its compiled `glum` and LightGBM
dependencies do not conflict with another project.

## Work from a checkout

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git,
then run these commands in a terminal. The checkout is the install route until
the first public release:

```bash
git clone https://github.com/ThomasBury/azoic.git
cd azoic
uv sync
uv run python -c "import azoic; print(azoic.__version__)"
uv run azoic --help
```

Keep this terminal in the `azoic` directory for the
[first model](first-model.md). `uv run` uses the checkout's `.venv`; you do not
need to activate it. `uv sync` also installs the default development tools,
but running the test suite is not required to fit your first model.

!!! note "Pending first public release"

    These instructions use the checkout. The planned first PyPI release is
    0.4.1; do not substitute a registry install for this checkout workflow.

## Optional extras

Core installation already includes pandas 3.0 or later, scikit-learn 1.6 or
later, glum, LightGBM, matplotlib, and xlsx export. `RiskGLM`, `RiskGBM`, and `FrequencySeverityModel`
automatically convert pandas `str`, nullable `string`, and `object` predictors
to categories. Numeric columns and declared category order/unused levels are
preserved, and caller frames are unchanged. Add only the integration you use.

| Extra | Install command | Adds |
|---|---|---|
| AWS | `uv sync --extra aws` | S3 Parquet access through `s3fs` |
| MLflow | `uv sync --extra mlops` | `azoic.mlops.log_run` |
| Tuning | `uv sync --extra tune` | Optuna and `azoic tune` |
| Plot | `uv sync --extra plot` | The interactive comparison dashboard |
| Several | `uv sync --extra mlops --extra tune --extra plot` | All named integrations in one environment |

Run these commands from the checkout, then use `uv run` for Python and CLI
commands. Include every extra you want to retain in later `uv sync` commands;
[a sync removes unselected extras](https://docs.astral.sh/uv/concepts/projects/sync/).

!!! info "Optional means import-time optional"

    MLflow, Optuna, Plotly, and S3 support are imported only by the feature that
    needs them. A missing extra raises an error with its install command; it does
    not prevent importing Azoic.

## Contributor checks

These checks are for changes to Azoic, separate from the first-model workflow.
Install every extra/group before running the complete quality gate:

```bash
uv sync --all-extras --all-groups
just check
```

For runtime dependencies only, use `uv sync --no-dev` and `uv run --no-dev`.

## Build the documentation

The site uses Zensical from the `docs` dependency group.

```bash
uv sync --group docs
just docs-build
```

The strict build writes the ignored site to `site/`.

## Render the tutorial series

The numbered executable tutorial chapters need the Jupyter demo group, the
MLflow, Plotly, and tuning extras, and a separate
[Quarto](https://quarto.org/docs/get-started/) installation.

```bash
uv sync --group demo --extra mlops --extra plot --extra tune
quarto --version
just demo
```

`just demo` renders the whole Quarto book under `examples/` into the ignored
`examples/_book/` directory. The render fetches public OpenML data for the
freMTPL2 chapters; the temporal-stability chapter is synthetic and
network-free. Automated tests and the First Model page remain network-free.

## Common failures

| Symptom | Cause | Fix |
|---|---|---|
| Python version resolution fails | The interpreter is older than 3.12 | Install Python 3.12 and rerun `uv sync` |
| `No matching distribution` for glum or LightGBM | Unsupported Python or platform wheel | Confirm a supported 64-bit Python 3.12 environment before compiling from source |
| `ModuleNotFoundError: mlflow`, `optuna`, `plotly`, or `s3fs` | The matching optional extra is absent | Install only the extra named in the error |
| Tutorial MLflow reports an out-of-date database schema after an upgrade | The existing local SQLite store predates the installed MLflow version | Back up the database, then run `uv run mlflow db upgrade sqlite:///examples/_artifacts/fremtpl2/mlflow.db` from the checkout |
| `quarto: command not found` | Quarto is external to the Python environment | Install Quarto and ensure `quarto` is on `PATH` |
| `just: command not found` | `just` is a task runner, not a Python dependency | Run the underlying `uv run ...` command shown in `justfile` or install `just` |
| LightGBM cannot load a shared library | A system OpenMP runtime is missing | Install the platform OpenMP runtime, then reinstall LightGBM |
| S3 loading reports a missing filesystem implementation | The AWS extra is absent | Run `uv sync --extra aws` and retry the same path |

[Fit a first model](first-model.md){ .md-button .md-button--primary }
[Read the configuration reference](../reference/configuration-cli.md){ .md-button }
