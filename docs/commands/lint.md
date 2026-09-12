# `devops lint`

Run static analysis checks and automatically apply fixes (ruff check --fix).

## Commands

## `devops lint`

**Run ruff linter across the project, automatically applying fixes by default.**

```bash
devops lint [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fix`, `--no-fix` | `boolean` | `True` | Auto-fix violations where possible. |
| `--check` | `boolean` | - | Check linting without applying automated fixes. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---
