# Azoic dev commands. Requires uv and just.
# Run `just --list` to see all targets.

default:
    @just --list

# Install runtime dependencies only.
sync-runtime:
    uv sync --no-dev

# Install the default development environment.
sync:
    uv sync

# Install all extras and dependency groups.
sync-all:
    uv sync --all-extras --all-groups

# Run tests, fail fast.
test:
    uv run pytest -x

# Run the whole test suite.
test-all:
    uv run pytest

# Lint only.
lint:
    uv run ruff check .

# Format.
format:
    uv run ruff format .

# Lint + source types + tests (run before committing).
check:
    uv run ruff check . && uv run ty check && uv run pytest

# Render the executable freMTPL2 tutorial (Quarto must be on PATH).
demo:
    uv run quarto render examples/fremtpl2.qmd --to html

# Build the static documentation site.
docs-build:
    uv run zensical build --strict

# Install pre-commit hooks once.
install-hooks:
    uv run pre-commit install
