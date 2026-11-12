# Contributing to Azoic

For package usage, start with the [documentation](https://thomasbury.github.io/azoic/).
For maintenance work, read [current work](development/README.md) and the relevant
[design contracts](development/design.md). Coding agents start at [AGENTS.md](AGENTS.md).

## Set up a checkout

Install Python 3.12, [uv](https://docs.astral.sh/uv/) and
[just](https://just.systems/), then run:

```bash
git clone https://github.com/ThomasBury/azoic.git
cd azoic
uv sync --locked --all-extras --all-groups
just check
```

Contributor checks need the optional integrations as well as development tools;
plain `uv sync` does not install everything needed for type-checking. The lockfile
is the full-check environment; runtime compatibility installs are tested separately.
No optional integration needs an external service for the automated tests.

## Checks and documentation

Run commands from the repository root. `just --list` lists all recipes.

| Task | Command |
| --- | --- |
| Lint, production types and all tests | `just check` |
| Fail-fast tests | `uv run pytest -x` |
| Focused test | `uv run pytest tests/test_models.py` |
| Lint only | `uv run ruff check .` |
| Production types only | `uv run ty check` |
| Format | `uv run ruff format .` |
| Strict documentation build | `just docs-build` |
| Render the tutorial book | `just demo` |
| CLI smoke | `uv run azoic --help` |
| Install local pre-commit hooks | `just install-hooks` |

The tutorial render requires a separate [Quarto](https://quarto.org/) installation
and may fetch real data. Automated tests use synthetic data without network access.
Only source documents belong in Git; generated sites, tutorial HTML, caches,
portfolio data, workbooks, reports and MLflow state remain ignored.

For smaller usage environments, `uv sync --no-dev` installs runtime dependencies,
`uv sync` installs the default development group, and `uv sync --extra NAME`
enables one optional integration. `uv sync --group demo --extra mlops` supplies
the tutorial stack. These do not replace the full contributor setup above.

## Making a change

- Keep one independently reviewable task per change and preserve unrelated work.
- Follow [agent engineering rules](AGENTS.md#code-style) and
  [actuarial rules](AGENTS.md#actuarial-rules), whether working manually or with an agent.
- Add focused behavioral coverage for non-trivial changes; reuse the seeded
  synthetic fixtures and existing estimator checks.
- Run `just check` before handoff or commit, `just docs-build` for documentation
  changes, and `git diff --check`. Describe checks actually run and any limits.
- Use `feat:`, `fix:`, `chore:`, `docs:` or `test:` commit prefixes. Describe the
  problem, resulting behavior and relevant validation in the pull request.
- Update public documentation and the changelog for user-facing changes. Update
  the current-work checkpoint for maintenance work and design contracts when they change.

## Keeping maintenance records small

`development/README.md` owns current status, unfinished acceptance and the latest
checkpoint. `development/design.md` owns durable architecture and decisions;
public API explanations stay in `docs/`. Root `AGENTS.md` owns agent instructions.
Link to the canonical page instead of copying its contents.

Create a separate plan under `development/` only when the task needs one. Once
complete, move detailed plans/checkpoints into `development/archive/`, leaving
only the current summary and links. Archived records preserve evidence, not
current task instructions or permission to publish. Do not add new root planning files.
