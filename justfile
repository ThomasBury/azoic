# RiskForge dev commands. Requires uv and just.
# Run `just --list` to see all targets.

default:
    @just --list

# Install core + dev (no extras). Use `just sync-all` for everything.
sync:
    uv sync

# Install all extras.
sync-all:
    uv sync --all-extras

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

# Lint + tests (run before committing).
check:
    uv run ruff check . && uv run pytest

# Install pre-commit hooks once.
install-hooks:
    uv run pre-commit install