# Code Library: Ruff, Mypy & Pytest (Core Developer Quality Suite)

## 1. Project References

| Resource | Endpoint / URL |
| :--- | :--- |
| **Official Documentation** | [docs.astral.sh/ruff/](https://docs.astral.sh/ruff/) • [mypy.readthedocs.io](https://mypy.readthedocs.io/) • [docs.pytest.org](https://docs.pytest.org/) |
| **Public Git Repository** | [github.com/astral-sh/ruff](https://github.com/astral-sh/ruff) • [github.com/python/mypy](https://github.com/python/mypy) • [github.com/pytest-dev/pytest](https://github.com/pytest-dev/pytest) |
| **Official PyPI Packages** | `ruff==0.16.4`, `mypy==2.3.1`, `pytest==9.1.1`, `pytest-cov==7.1.0`, `pytest-xdist==3.8.0`, `pytest-asyncio==1.4.0`, `pytest-mock==3.15.1` |
| **DevOps CLI Integration** | [`src/devops_cli/commands/ci.py`](file:///workspaces/devops-cli/src/devops_cli/commands/ci.py) • [`pyproject.toml`](file:///workspaces/devops-cli/pyproject.toml) |

---

## 2. General Information & Architecture

**Ruff**, **Mypy**, and **Pytest** form the foundational three-pillar quality assurance suite powering the 10-point `devops ci` quality gate.
- **Ruff**: An extremely fast Python linter and formatter written in Rust that replaces Flake8, Black, isort, and pyupgrade, running 10x–100x faster than traditional tools.
- **Mypy**: The static type checker validating 100% strict type safety across all function signatures with `mypy --strict`.
- **Pytest**: The industry-standard testing framework combined with `pytest-xdist` (multi-core parallel testing), `pytest-cov` ($\ge 90\%$ coverage enforcement), `pytest-asyncio`, and `pytest-mock`.

---

## 3. Comparable Projects & Tradeoffs

| Tool | Strengths | Weaknesses | Why `devops-cli` Chose This Suite |
| :--- | :--- | :--- | :--- |
| **`ruff`** | 100x faster (Rust), combines 40+ linter plugins into one tool, instant autofixes (`--fix`), replaces Black/Flake8/isort. | Newer than legacy Flake8. | **Selected**: Essential for instant sub-second CI validation loops. |
| **`mypy`** | Canonical reference type checker, strict Pydantic v2 plugin support, exact PEP 484/526 compliance. | Slower than Pyright on massive codebases. | **Selected**: The gold standard for production Python type safety. |
| **`pytest` + plugins** | Powerful fixtures, parallel execution (`-n auto`), async testing, rich assertion introspection. | Extensive plugin configuration. | **Selected**: Indispensable test runner across Python open source. |
| **`black` + `flake8`** | Legacy standard Python formatting/linting. | 50x slower, requires managing multiple separate tools and configs. | Superseded by Ruff. |

---

## 4. Key Concepts & Core Patterns

1. **Ruff Ruleset Configuration (`pyproject.toml`)**:
   ```toml
   [tool.ruff.lint]
   select = ["E", "F", "I", "N", "W", "UP"]
   ```
2. **Strict Mypy Invariants**:
   - Disallows untyped `def` functions.
   - Enforces Pydantic model type checking via `pydantic.mypy` plugin.
3. **Pytest Coverage Threshold**:
   - `pytest --cov=src --cov-fail-under=90` enforces strict minimum 90% code coverage.

---

## 5. Common & Advanced Usage Examples

### Full Quality Gate Execution
```bash
# Run complete 10-point quality gate
devops ci

# Targeted lint and auto-format
uv run ruff check . --fix
uv run ruff format .

# Strict static typecheck
uv run mypy src

# Parallel test execution with code coverage
uv run pytest -n auto --cov=src --cov-report=term-missing
```

---

## 6. Best Practices & Security Standards

1. **Zero Type Errors Permitted**: All modified modules must pass `mypy --strict` with zero errors.
2. **Defensive Test Isolation**: Unit tests must isolate external networks, LLMs, and subprocesses using `pytest-mock` or deterministic fixtures.
3. **Maintain $\ge 90\%$ Code Coverage**: Every new feature or refactor must supply corresponding unit tests to prevent coverage drops below the mandatory threshold.
