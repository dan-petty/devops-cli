# `devops ci`

Run tests, linting, formatting, and type-checks.

## Commands

## `devops ci test`

**Run the pytest test suite in parallel leveraging all CPU cores.**

```bash
devops ci test [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--verbose`, `-v` | `boolean` | - | Verbose output |
| `-k` | `string` | - | Filter tests by keyword expression |
| `-x` | `boolean` | - | Stop after first failure |
| `-n`, `--numprocesses` | `string` | `auto` | Number of parallel worker processes |

---

## `devops ci coverage`

**Run pytest with parallel code coverage analysis over src/.**

```bash
devops ci coverage [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--html` | `boolean` | - | Generate HTML coverage report in htmlcov/ |
| `-n`, `--numprocesses` | `string` | `auto` | Number of parallel worker processes |

---

## `devops ci lint`

**Run ruff linter across the project.**

```bash
devops ci lint [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fix` | `boolean` | - | Auto-fix violations where possible |

---

## `devops ci format`

**Check (or apply) code formatting with ruff format.**

```bash
devops ci format [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fix` | `boolean` | - | Apply formatting changes in-place |

---

## `devops ci typecheck`

**Run mypy static type-checker strictly targeting Python 3.14 over src/.**

```bash
devops ci typecheck
```

---

## `devops ci audit`

**Run uv audit to check for known package vulnerabilities.**

```bash
devops ci audit
```

---

## `devops ci security`

**Run bandit static security vulnerability analysis over src/.**

```bash
devops ci security [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--severity`, `-s` | `string` | `medium` | Minimum severity threshold (low, medium, high) |

---

## `devops ci actionlint`

**Run actionlint to validate GitHub Actions workflows for syntax and schema errors.**

```bash
devops ci actionlint
```

---

## `devops ci docs`

**Verify that documentation is up to date with CLI commands and configuration.**

```bash
devops ci docs
```

---

## `devops ci run`

**Run full CI and return a single pass/fail status.**

```bash
devops ci run [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fix`, `--no-fix` | `boolean` | `True` | Auto-fix lint/format before reporting status |

---
