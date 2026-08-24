# Knowledge Base: Ruff, Mypy & Pytest (Python Engineering Quality Suite)

## 1. Overview & Purpose

The Python engineering quality suite in `devops-cli` comprises three modern, industry-standard tools:
1. **Ruff**: An extremely fast Python linter and code formatter written in Rust, replacing Flake8, Black, isort, and pyupgrade.
2. **Mypy**: The static type checker for Python, configured in strict mode (`--strict`) to guarantee 100% type safety and catch subtle runtime bugs.
3. **Pytest**: The feature-rich testing framework, paired with `pytest-xdist` for multi-core parallel test execution, `pytest-cov` for branch coverage analysis, and `pytest-mock`.

---

## 2. Usage Information & Architecture

- **Ruff Configuration (`pyproject.toml`)**:
  - Target Python version: `py314`.
  - Line length limit: 100 characters.
  - Selected rules: `E`, `F`, `W`, `I` (isort), `UP` (pyupgrade), `B` (bugbear), `SIM` (simplify), `C4` (comprehensions), `T20` (print checks), `RUF`.
- **Mypy Strict Configuration**:
  - `strict = true`, `disallow_untyped_defs = true`, `disallow_incomplete_defs = true`, `warn_unused_ignores = true`.
- **Pytest Parallel Execution**:
  - `addopts = "-n auto --dist loadscope --cov=src/devops_cli --cov-report=term-missing"`.
- **CI Quality Gate**: Unified under `devops ci` (`devops ci lint`, `devops ci format`, `devops ci typecheck`, `devops ci test`).

---

## 3. Common & Advanced Commands

### DevOps CLI Quality Subcommands
```bash
# Execute full CI gate across all 10 checks
devops ci

# Execute unit tests with optional verbosity and filtering
devops ci test -v -k "test_server"

# Run Ruff linter with automatic fix
devops ci lint --fix

# Run Ruff formatter in fix mode
devops ci format --fix

# Run strict Mypy type check
devops ci typecheck
```

### Direct Tool Invocations via `uv`
```bash
# Fast lint check on modified files
uv run ruff check path/to/file.py

# Format files
uv run ruff format path/to/file.py

# Typecheck modified modules with strict type inference
uv run mypy src/devops_cli/server src/devops_cli/commands/serve.py

# Run targeted pytest on specific file with parallel workers
uv run pytest tests/test_server.py -n auto

# Run tests and generate HTML coverage report
uv run pytest --cov=src/devops_cli --cov-report=html:coverage_html
```

---

## 4. Best Practice Guidance

1. **Progressive Verification**: During active coding loops, run isolated checks (`uv run ruff check <file>`, `uv run pytest <test_file>`); only run full test suites prior to commit/PR milestones.
2. **Modern Python 3.14+ Idioms**:
   - Use `from __future__ import annotations`.
   - Use union syntax `A | B` instead of `Union[A, B]` or `Optional[T]`.
   - Use standard collections `list[str]`, `dict[str, Any]`, `set[int]`.
3. **Deterministic Test Isolation**:
   - Mock all network I/O, subprocesses, and external LLM providers in unit tests.
   - Use `tmp_path` fixtures for filesystem tests to prevent state leakage.
4. **Zero Flakiness**: Ensure tests never depend on wall-clock timings or non-deterministic dictionary iterations.

---

## 5. Security Recommendations & Zero-Trust Policies

- **No Secrets in Test Code**: Never use real user tokens or live cloud endpoints in test fixtures.
- **Coverage Enforcement**: Maintain at least 70% line and branch test coverage across all core CLI command modules and security subsystems.

---

## 6. General Standards & Reference Guidelines

- **Config File**: All tool configurations reside centrally in [`pyproject.toml`](../../../pyproject.toml).
- **Test File Naming**: All test modules must be named `tests/test_<feature>.py`.

---

## 7. Official References & Published Artifacts

- **Ruff Homepage**: [astral.sh/ruff](https://astral.sh/ruff) | [github.com/astral-sh/ruff](https://github.com/astral-sh/ruff)
- **Mypy Homepage**: [mypy-lang.org](https://mypy-lang.org/) | [github.com/python/mypy](https://github.com/python/mypy)
- **Pytest Homepage**: [pytest.org](https://docs.pytest.org/) | [github.com/pytest-dev/pytest](https://github.com/pytest-dev/pytest)
- **Official PyPI Packages**:
  - [pypi.org/project/ruff](https://pypi.org/project/ruff/)
  - [pypi.org/project/mypy](https://pypi.org/project/mypy/)
  - [pypi.org/project/pytest](https://pypi.org/project/pytest/)
- **DevOps CLI CI Quality Command**: [src/devops_cli/commands/ci.py](../../../src/devops_cli/commands/ci.py)
