# Python standards

The Python development standard for this repo. Distilled from the
[etoews/python-standards](https://github.com/etoews/python-standards) reference notes
([`MAC.md`](https://github.com/etoews/python-standards/blob/HEAD/MAC.md) and
[`PROJECT.md`](https://github.com/etoews/python-standards/blob/HEAD/PROJECT.md)) and
narrowed to what Python work in *this* repo actually needs.

This repo is a collection of Claude skills. The only Python in it today is the
[`ai-eval`](../../skills/ai-eval/) skill: a uv-managed project with `scripts/`,
`tests/`, `pyproject.toml`, and a committed `uv.lock`. Follow this file for any
Python work here. For the exhaustive per-project playbook and one-time machine
setup, read the [etoews/python-standards](https://github.com/etoews/python-standards) reference.

## Stack

| Purpose | Tool | Notes |
|---|---|---|
| Deps and envs | **uv** | The only way in. Never bare `pip`. |
| Lint and format | **ruff** | One tool; replaces black, isort, flake8, pyupgrade. |
| Tests | **pytest** | `tests/` at project root, no `__init__.py`. |
| Type check | **ty** | Pre-1.0; fall back to mypy per-project if it blocks. |
| Logging | stdlib `logging` | Never `print()` for diagnostics. |
| CLI | **argparse** or **Typer** | argparse for a single command; Typer once it grows. |

## uv is the only way in

- All Python work uses uv. Never run bare `pip install` (it fails anyway under
  `PIP_REQUIRE_VIRTUALENV=1`).
- Add deps: `uv add <pkg>` (runtime), `uv add --dev <pkg>` (dev). Remove with
  `uv remove <pkg>`. After pulling: `uv sync`.
- Run everything through the project venv: `uv run <cmd>` (for example
  `uv run python scripts/run_eval.py`, `uv run pytest`).
- Commit `pyproject.toml`, `uv.lock`, and `.python-version`. Gitignore `.venv/`.

## Project layout for a skill

A skill's Python lives beside its `SKILL.md`:

```
skills/<skill>/
  SKILL.md
  pyproject.toml
  uv.lock
  .python-version
  scripts/          # flat modules, run in place
  tests/            # flat, no __init__.py
```

- A skill is read and run in place (`uv run python scripts/x.py`), not installed
  as a package, so the packaged `src/` layout from the reference does not apply.
  Keep modules flat under `scripts/` and tests flat under `tests/`.
- Reach for the `src/` layout only if a tool here ever becomes a genuinely
  installable or publishable package. That is not the case today.

## pyproject.toml

Single source of truth for metadata, deps, and tool config.

- **Lower-bound pins only** in `[project.dependencies]`: `foo>=2.32`. `uv.lock`
  owns the upper bound. Pin exactly only for a known incompatibility, with a
  one-line comment giving the reason.
- **Dev deps** go in `[dependency-groups]` under `dev` (`uv add --dev` writes
  there).
- **`requires-python`** matches the project's real support window. Prefer the
  current default (3.14) for new work, but a heavy-dependency project may need a
  narrower range: `ai-eval` pins `>=3.10,<3.13` for arize-phoenix and litellm.
  Keep it as tight as the deps demand and no tighter.
- Tool config (`[tool.ruff]`, `[tool.pytest.ini_options]`, `[tool.ty]`) lives
  here rather than in scattered dotfiles.

## Ruff (lint and format)

```
uv run ruff check --fix      # lint with autofix
uv run ruff format           # format
```

- Rule selection in `[tool.ruff.lint]`: `E`, `F`, `I`, `UP`, `B`, `SIM`, `RUF`.
- Per-file ignores for tests: `S101` (pytest uses asserts) and `D` (tests need
  no docstrings).
- In CI, run `ruff format --check` (fails if unformatted) and `ruff check` (no
  `--fix`).

## Pytest

- `tests/` at project root, no `__init__.py`, mirroring the module structure.
- Config in `[tool.pytest.ini_options]`:
  ```toml
  testpaths = ["tests"]
  addopts = "-ra --strict-markers --strict-config"
  ```
- **Parametrize, do not loop**: a loop hides every failure after the first.
- Structure each test as Arrange-Act-Assert, separated by blank lines.
- Coverage is available (`--cov`), but do not gate CI on it until the suite is
  mature.

## ty (type check)

```
uv run ty check
```

- **Everything is typed.** Every function and method gets a full signature,
  parameters and return, in both `scripts/` and `tests/`, including `-> None`.
- **Modern syntax only**: `list[int]`, `dict[str, X]`, `X | None`. No
  `typing.List`, `typing.Dict`, or `typing.Optional`.
- `ty check` runs clean on every commit; CI fails on type errors.
- Suppress with a specific rule only: `# type: ignore[arg-type]`, never a bare
  `# type: ignore`.
- ty is pre-1.0. If it blocks a legitimate typing pattern, swap it for mypy on
  *that* project and note the swap in the README.

## Docstrings

Google style. Document **intent, not mechanics**: preconditions the caller must
meet, what "empty" or "missing" means, exceptions raised and when, non-obvious
side effects. A one-line docstring is fine for an obvious function.

## Logging

- stdlib `logging`. Module-level logger: `logger = logging.getLogger(__name__)`.
  Never the root logger.
- Use `%` formatting for lazy evaluation, not f-strings:
  `logger.debug("fetched %s items", len(items))`.
- CLI **output** to stdout is fine (`print`, `typer.echo`). CLI **diagnostics**
  go through `logging` to stderr. Do not conflate the two channels.
- Never log secrets, tokens, or PII. Log identifiers, not contents.

## Error handling

- Raise specific exceptions, not bare `Exception`. Catch at boundaries (the seam
  where your code meets an external library) and chain with `raise ... from e`.
- Never a bare `except:`; use `except Exception:` at minimum. An `except ...:
  pass` needs a one-line comment saying why it is safe.
- Once a project is large enough to need its own exception hierarchy, put it in
  `exceptions.py` with a project base class. A small single-command script can
  raise stdlib exceptions directly.

## Config and secrets

- Provider API keys come from a gitignored `.env`, loaded once at the entry
  point (`python-dotenv`'s `load_dotenv()`, or `pydantic-settings` for anything
  with more than a couple of typed settings). Nothing deep in the call stack
  reaches into `os.environ`.
- Required config has no default: missing config fails fast at startup.
- Commit a `.env.example` documenting every key with placeholder values.
- In production, secrets come from the host's environment, not a `.env` file.

## Not needed here

- `src/` packaging, wheels, PyPI publishing, and end-user optional-dependency
  extras. Skills are not distributed as packages.
- Typer and rich, unless a skill grows a genuine multi-command CLI. argparse is
  fine for a single-command script like `run_eval.py`.

## Quick reference

| Command | Purpose |
|---|---|
| `uv add <pkg>` / `uv add --dev <pkg>` | Add a runtime / dev dependency |
| `uv remove <pkg>` | Remove a dependency |
| `uv sync` | Install locked deps into `.venv` |
| `uv sync --locked` | Same, but fail if the lockfile is stale (CI) |
| `uv run python scripts/<x>.py` | Run a script in the project venv |
| `uv run pytest` | Tests |
| `uv run ruff check --fix` | Lint and autofix |
| `uv run ruff format` | Format |
| `uv run ty check` | Type check |
