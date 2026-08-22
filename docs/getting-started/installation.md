# Installation

Azoic requires Python 3.12 or newer. Use a virtual environment so its compiled
`glum` and LightGBM dependencies do not conflict with another project.

## Install the package

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

Core installation already includes pandas, scikit-learn, glum, LightGBM,
matplotlib, and xlsx export. Add only the integration you use.

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

## Work from a checkout

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

## Build the documentation

The site uses Zensical from the `docs` dependency group.

```bash
uv sync --group docs
just docs-build
```

The strict build writes the ignored site to `site/`.

## Render the freMTPL2 tutorial

The executable tutorial needs the Jupyter demo group, the MLflow and Plotly
extras, and a separate [Quarto](https://quarto.org/docs/get-started/) installation.

```bash
uv sync --group demo --extra mlops --extra plot
quarto --version
just demo
```

The render fetches public OpenML data. Automated tests and the First Model page
remain network-free.

## Common failures

| Symptom | Cause | Fix |
|---|---|---|
| Python version resolution fails | The interpreter is older than 3.12 | Install Python 3.12 and rerun `uv sync`, or create a 3.12 virtual environment for pip |
| `No matching distribution` for glum or LightGBM | Unsupported Python or platform wheel | Confirm a supported 64-bit Python 3.12 environment before compiling from source |
| `ModuleNotFoundError: mlflow`, `optuna`, `plotly`, or `s3fs` | The matching optional extra is absent | Install only the extra named in the error |
| `quarto: command not found` | Quarto is external to the Python environment | Install Quarto and ensure `quarto` is on `PATH` |
| `just: command not found` | `just` is a task runner, not a Python dependency | Run the underlying `uv run ...` command shown in `justfile` or install `just` |
| LightGBM cannot load a shared library | A system OpenMP runtime is missing | Install the platform OpenMP runtime, then reinstall LightGBM |
| S3 loading reports a missing filesystem implementation | The AWS extra is absent | Install `azoic[aws]` and retry the same path |

[Fit a first model](first-model.md){ .md-button .md-button--primary }
[Read the configuration reference](../reference/configuration-cli.md){ .md-button }
