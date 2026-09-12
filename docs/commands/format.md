# `devops format`

Automatically apply code formatting in-place (ruff format).

## Commands

## `devops format`

**Format codebase with ruff format (or verify in check-only mode with --check).**

```bash
devops format [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--check` | `boolean` | - | Check formatting without writing changes to files. |
| `--fix`, `--no-fix` | `boolean` | `True` | Apply formatting changes in-place. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---
