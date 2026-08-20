# CI & Quality Gates Tool Cheatsheet

Compare disparate linters, formatters, type checkers, and test runners with the unified `devops ci` quality gate pipeline.

---

## 1. Quality Gates & Validation Suite

| Action / Goal | Original Command | `devops-cli` Command | Key Enhancements in `devops-cli` |
| :--- | :--- | :--- | :--- |
| **Run Full CI Validation** | `ruff format && ruff check && mypy && pytest && bandit ...` | `devops ci` | Single command executing 10 validation stages (format, lint, typecheck, test, coverage, audit, security, actionlint, docs, version). |
| **Format Codebase** | `ruff format .` | `devops ci format` | Formats all source files to project PEP 8 standards with strict 100-character line length. |
| **Lint Codebase** | `ruff check . --fix` | `devops ci lint [--fix]` | Validates and auto-fixes lint errors, import ordering, and modernization rules. |
| **Strict Type Checking** | `mypy src --strict` | `devops ci typecheck` | Runs Mypy strict type checking across all packages. |
| **Unit & Integration Tests**| `pytest -n auto --maxprocesses=4` | `devops ci test` | Executes parallel pytest suite with auto-configured process pooling. |
| **Coverage Measurement** | `pytest --cov=src --cov-report=html` | `devops ci coverage [--html]` | Computes coverage percentages and generates interactive HTML coverage reports in `.data/coverage/`. |
| **GitHub Actions Linting** | `actionlint .github/workflows/*.yml` | `devops ci actionlint` | Validates YAML syntax, context expressions, and security permissions in GitHub Actions workflows. |
| **Doc Freshness Check** | `python tools/check_docs.py` | `devops ci docs` | Asserts that CLI command reference and README command matrix match live Typer definitions. |

---

## 2. CI Pipeline Configuration

In GitHub Actions workflows (`.github/workflows/ci.yml`), developers can replace lengthy multi-step lint scripts with a single authoritative gate:

```yaml
- name: Run Full DevOps Quality Gate
  run: uv run devops ci
```
