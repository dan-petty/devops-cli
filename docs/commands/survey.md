# `devops survey`

Outward-facing capability and upstream maturity survey.

## Commands

## `devops survey`

**Outward-facing capability and upstream maturity survey.**

```bash
devops survey [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--format`, `-f` | `string` | `table` | Output format (table, json, yaml). |
| `--json`, `-j` | `boolean` | - | Emit survey results in structured JSON. |
| `--config`, `-c` | `path` | - | Path to survey configuration TOML. |
| `--emit-candidates` | `boolean` | - | Emit discovered capability gaps as roadmap candidates. |
| `--confirm` | `boolean` | - | Confirm and apply candidate filing to roadmap. |
| `--repo`, `-R` | `string` | - | Target GitHub repository in owner/repo format. |
| `--dependencies-only` | `boolean` | - | Run upstream dependency maturity survey only. |
| `--capabilities-only` | `boolean` | - | Run comparable tools capability survey only. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---
