# `devops research`

Read what the project pins and watch the upstream of each pin.

## Commands

## `devops research inventory`

**List every pin of the project as a typed component: Python packages, tools, container images, GitHub Actions, Helm charts and Terraform providers. It reads files only.**

```bash
devops research inventory [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--root` | `path` | - | Root of the repository to read. Default: the repository of the current directory. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--json`, `-j` | `boolean` | - | Output findings or metrics as JSON. |

---

## `devops research advisories`

**List the advisories that affect the pins of the project. It asks OSV about the Python and Node packages, and counts the components that OSV cannot match.**

```bash
devops research advisories [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--root` | `path` | - | Root of the repository to read. Default: the repository of the current directory. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--json`, `-j` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---
