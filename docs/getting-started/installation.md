# Installation

Azoic requires Python 3.12 or newer and pandas 3.0 or newer. pandas 2 is no
longer supported. Use a virtual environment so its compiled `glum` and LightGBM
dependencies do not conflict with another project.

## Work from a checkout

The checkout is the only install route until the first public release lands on
PyPI:

```bash
git clone https://github.com/ThomasBury/azoic.git
cd azoic
uv sync
uv run pytest -x
```

`uv sync` installs the default development group. Other useful environments are:

| Goal | Command |
|---|---|
| Runtime only | `uv sync --no-dev` |
| Default contributor environment | `uv sync` |
| Every extra and dependency group | `uv sync --all-extras --all-groups` |
| Lint, type-check, and test | `just check` |

## Install from PyPI

!!! note "Pending first public release"

    `azoic` is not on PyPI yet; the 0.4.1 release publishes it. Until then
    `uv add azoic` and `pip install azoic` fail with `No matching
    distribution` -- use the checkout above.

With [uv](https://docs.astral.sh/uv/):

```bash
uv add azoic
```

With pip:

```bash
python -m pip install azoic
```

Verify the environment:

```bash
python -c "import azoic; print(azoic.__version__)"
azoic --help
```

## Optional extras

Core installation already includes pandas 3.0 or later, scikit-learn 1.6 or
later, glum, LightGBM, matplotlib, and xlsx export. `RiskGLM`, `RiskGBM`, and `FrequencySeverityModel`
automatically convert pandas `str`, nullable `string`, and `object` predictors
to categories. Numeric columns and declared category order/unused levels are
preserved, and caller frames are unchanged. Add only the integration you use.

| Extra | Install command | Adds |
|---|---|---|
| AWS | `uv add "azoic[aws]"` | S3 Parquet access through `s3fs` |
| MLflow | `uv add "azoic[mlops]"` | `azoic.mlops.log_run` |
| Tuning | `uv add "azoic[tune]"` | Optuna and `azoic tune` |
| Plot | `uv add "azoic[plot]"` | The interactive comparison dashboard |
| Several | `uv add "azoic[mlops,tune,plot]"` | All named integrations in one environment |

For pip, replace `uv add` with `python -m pip install`.

!!! info "Optional means import-time optional"

    MLflow, Optuna, Plotly, and S3 support are imported only by the feature that
    needs them. A missing extra raises an error with its install command; it does
    not prevent importing Azoic.

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
| Python version resolution fails | The interpreter is older than 3.12 | Install Python 3.12 and rerun `uv sync`, or create a 3.12 virtual environment for pip |
| `No matching distribution` for glum or LightGBM | Unsupported Python or platform wheel | Confirm a supported 64-bit Python 3.12 environment before compiling from source |
| `ModuleNotFoundError: mlflow`, `optuna`, `plotly`, or `s3fs` | The matching optional extra is absent | Install only the extra named in the error |
| Tutorial MLflow reports an out-of-date database schema after an upgrade | The existing local SQLite store predates the installed MLflow version | Back up the database, then run `uv run mlflow db upgrade sqlite:///examples/_artifacts/fremtpl2/mlflow.db` from the checkout |
| `quarto: command not found` | Quarto is external to the Python environment | Install Quarto and ensure `quarto` is on `PATH` |
| `just: command not found` | `just` is a task runner, not a Python dependency | Run the underlying `uv run ...` command shown in `justfile` or install `just` |
| LightGBM cannot load a shared library | A system OpenMP runtime is missing | Install the platform OpenMP runtime, then reinstall LightGBM |
| S3 loading reports a missing filesystem implementation | The AWS extra is absent | Install `azoic[aws]` and retry the same path |

[Fit a first model](first-model.md){ .md-button .md-button--primary }
[Read the configuration reference](../reference/configuration-cli.md){ .md-button }
