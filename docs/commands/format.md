# `devops format`

Automatically apply code formatting in-place (ruff format).

## Commands

## `devops format test`

**Run the pytest test suite in parallel leveraging all CPU cores.**

```bash
devops format test [OPTIONS]
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

## `devops format coverage`

**Run pytest with parallel code coverage analysis over src/.**

```bash
devops format coverage [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--html` | `boolean` | - | Generate HTML coverage report in .data/htmlcov/. |
| `--xml` | `boolean` | - | Generate XML coverage report in .data/coverage.xml. |
| `-n`, `--numprocesses` | `string` | `auto` | Number of parallel worker processes. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops format lint`

**Run ruff linter across the project, automatically applying fixes by default.**

```bash
devops format lint [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fix`, `--no-fix` | `boolean` | `True` | Auto-fix violations where possible. |
| `--check` | `boolean` | - | Check linting without applying automated fixes. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops format format`

**Format codebase with ruff format (or verify in check-only mode with --check).**

```bash
devops format format [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--check` | `boolean` | - | Check formatting without writing changes to files. |
| `--fix`, `--no-fix` | `boolean` | `True` | Apply formatting changes in-place. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops format typecheck`

**Run mypy static type-checker strictly targeting Python 3.14 over src/.**

```bash
devops format typecheck [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops format audit`

**Run uv audit to check for known package vulnerabilities.**

```bash
devops format audit [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops format security`

**Run bandit static security vulnerability analysis over src/.**

```bash
devops format security [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--severity`, `-s` | `string` | `medium` | Minimum severity threshold (low, medium, high). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops format actionlint`

**Run actionlint to validate GitHub Actions workflows for syntax and schema errors.**

```bash
devops format actionlint [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops format docs`

**Verify (or update with --fix) that documentation is up to date with CLI commands and configuration.**

```bash
devops format docs [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fix` | `boolean` | - | Synchronize Complete Command Matrix in README.md. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops format maintain`

**Run automated toolchain, dependency freshness, and lockfile maintenance checks.**

```bash
devops format maintain [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fix` | `boolean` | - | Automatically synchronize dependencies and lockfile. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops format run`

**Run full CI and return a single pass/fail status.**

```bash
devops format run [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fix`, `--no-fix` | `boolean` | `True` | Auto-fix lint/format before reporting status. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---
