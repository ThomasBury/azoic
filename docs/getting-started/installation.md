# Installation

Azoic requires Python 3.12 or newer and pandas 3.0 or newer. pandas 2 is no
longer supported. Use a virtual environment so its compiled `glum` and LightGBM
dependencies do not conflict with another project.

!!! note "Release and checkout documentation"

    The [first model](first-model.md) and the opening file-based
    [configuration example](../guide/experiment-configuration.md) target the
    published **0.5.0** package. The other guides and generated API reference
    describe the current **unreleased checkout**. Its package version still
    reads 0.5.0; that string alone does not establish API equivalence with PyPI.
    Use a checkout for sections labelled checkout-only.

## Tested environments

The package metadata permits Python 3.12 or newer. Validation covers the
environments below; it does not establish every Python, platform or dependency
combination:

| Environment | Validation |
|---|---|
| Python 3.12, locked all-extras/groups dependencies | Full tests, lint, source types and strict documentation build |
| Python 3.12, low compatible direct runtime versions | Fresh wheel and sdist installs, model/preprocessing checks, imports/version and all five CLI command helps |
| Python 3.14, current compatible runtime wheels | The same installed wheel/sdist checks; only Azoic's own sdist may be built from source |
| Python 3.12, Linux and Windows Server 2025, runtime dependencies | Exact documented starter and file-based configuration against PyPI 0.5.0 and a checkout-built wheel; workbook-rate agreement and CLI fit |

The installed starter passed its Python 3.12 CI matrix on Linux and Windows
Server 2025, against both the PyPI release and a checkout-built wheel. The Windows
jobs used Python 3.12.10. This validates the starter; the full test suite still
runs on Linux. macOS is unverified. Exact execution evidence is recorded in
`PROGRESS.md`.

The checkout requires `glum>=3.4.1` and `typer>=0.27.1`, replacing the earlier
`glum>=3.0` and `typer>=0.12` declarations. The low-version job reads direct
requirements from the built wheel's metadata and uses uv's `lowest-direct`
resolution: low compatible direct versions and current compatible transitive
versions. It asserts those exact glum/Typer floors. Compatibility installs use
runtime dependencies only and resolve independently of `uv.lock`; they do not
run the full suite or validate optional integrations on Python 3.14.

## Install from PyPI

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) first.
These project commands work in a Linux terminal and Windows PowerShell; no shell
activation is needed. In a new directory:

```bash
uv init --python 3.12 my-pricing-project
cd my-pricing-project
uv add azoic==0.5.0
uv run python -c "import azoic; print(azoic.__version__)"
uv run azoic --help
```

In an existing uv project, run just the last three commands. Then follow the
[first model](first-model.md); you do not need Git, Quarto or contributor tools.
With pip, activate a Python 3.12 virtual environment and run
`python -m pip install azoic==0.5.0`, then `python first_model.py`.

Registry extras use package notation, for example
`uv add 'azoic[mlops,tune]==0.5.0'` or
`python -m pip install 'azoic[mlops,tune]==0.5.0'`.

## Work from a checkout

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git,
then run these commands in a terminal. Use the checkout to develop Azoic or
render the executable tutorial:

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

## Optional extras

Core installation already includes pandas 3.0 or later, scikit-learn 1.6 or
later, glum, LightGBM, matplotlib, and xlsx export.

**Checkout behavior:** `RiskGLM`, `RiskGBM`, and `FrequencySeverityModel`
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
| `No matching distribution` for glum or LightGBM | Unsupported Python or platform wheel | Try 64-bit Python 3.12 and check the dependency wheel availability for your platform |
| `ModuleNotFoundError: mlflow`, `optuna`, `plotly`, or `s3fs` | The matching optional extra is absent | Install only the extra named in the error |
| Tutorial MLflow reports an out-of-date database schema after an upgrade | The existing local SQLite store predates the installed MLflow version | Back up the database, then run `uv run mlflow db upgrade sqlite:///examples/_artifacts/fremtpl2/mlflow.db` from the checkout |
| `quarto: command not found` | Quarto is external to the Python environment | Install Quarto and ensure `quarto` is on `PATH` |
| `just: command not found` | `just` is a task runner, not a Python dependency | Run the underlying `uv run ...` command shown in `justfile` or install `just` |
| LightGBM cannot load a shared library | A system OpenMP runtime is missing | Install the platform OpenMP runtime, then reinstall LightGBM |
| S3 loading reports a missing filesystem implementation | The AWS extra is absent | Run `uv sync --extra aws` and retry the same path |

For the first failed rule, checkout outcome-validation errors identify the
configured column, invalid-row count and first five **zero-based positions**
in the supplied frame. For example,
`row positions ... [0, 8]` means inspect `portfolio.iloc[[0, 8]]`, even if the
frame has duplicate or non-numeric index labels. Only positions are printed,
not policy identifiers or claim values. Correct the source data deliberately;
the loader does not drop, repair or cap it. Released 0.5.0 errors can be less
detailed.

[Fit a first model](first-model.md){ .md-button .md-button--primary }
[Read the configuration reference](../reference/configuration-cli.md){ .md-button }
