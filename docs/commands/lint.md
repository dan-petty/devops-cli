# `devops lint`

Run static analysis checks and automatically apply fixes (ruff check --fix).

## Commands

## `devops lint test`

**Run the pytest test suite in parallel leveraging all CPU cores.**

```bash
devops lint test [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--verbose`, `-v` | `boolean` | - | Enable detailed logging output. |
| `-k` | `string` | - | Filter tests by keyword expression. |
| `-x` | `boolean` | - | Stop after first failure. |
| `-n`, `--numprocesses` | `string` | `auto` | Number of parallel worker processes. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops lint coverage`

**Run pytest with parallel code coverage analysis over src/.**

```bash
devops lint coverage [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--html` | `boolean` | - | Generate HTML coverage report in .data/htmlcov/. |
| `--xml` | `boolean` | - | Generate XML coverage report in .data/coverage.xml. |
| `-n`, `--numprocesses` | `string` | `auto` | Number of parallel worker processes. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops lint lint`

**Run ruff linter across the project, automatically applying fixes by default.**

```bash
devops lint lint [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fix`, `--no-fix` | `boolean` | `True` | Auto-fix violations where possible. |
| `--check` | `boolean` | - | Check linting without applying automated fixes. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops lint format`

**Format codebase with ruff format (or verify in check-only mode with --check).**

```bash
devops lint format [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--check` | `boolean` | - | Check formatting without writing changes to files. |
| `--fix`, `--no-fix` | `boolean` | `True` | Apply formatting changes in-place. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops lint typecheck`

**Run mypy static type-checker strictly targeting Python 3.14 over src/.**

```bash
devops lint typecheck [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops lint audit`

**Run uv audit to check for known package vulnerabilities.**

```bash
devops lint audit [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops lint security`

**Run bandit static security vulnerability analysis over src/.**

```bash
devops lint security [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--severity`, `-s` | `string` | `medium` | Minimum severity threshold (low, medium, high). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops lint actionlint`

**Run actionlint to validate GitHub Actions workflows for syntax and schema errors.**

```bash
devops lint actionlint [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops lint docs`

**Verify (or update with --fix) that documentation is up to date with CLI commands and configuration.**

```bash
devops lint docs [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fix` | `boolean` | - | Synchronize Complete Command Matrix in README.md. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops lint maintain`

**Run automated toolchain, dependency freshness, and lockfile maintenance checks.**

```bash
devops lint maintain [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fix` | `boolean` | - | Automatically synchronize dependencies and lockfile. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops lint run`

**Run full CI and return a single pass/fail status.**

```bash
devops lint run [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fix`, `--no-fix` | `boolean` | `True` | Auto-fix lint/format before reporting status. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---
