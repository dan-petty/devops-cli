# `devops install-tools`

Install and manage DevOps tool binaries.

```bash
devops install-tools [OPTIONS] COMMAND [ARGS]...
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--tool`, `-t` | `string` | - | Install a specific tool. |
| `--target-dir`, `-d` | `path` | `~/.local/bin` | Target directory path for operation. |
| `--only-missing` | `boolean` | - | Only install tools that are not linked at their locked version, or whose command on PATH prints another version. |
| `--check` | `boolean` | - | Install nothing: report each tool not linked at its locked version, read the version the openspec command on PATH prints, and exit 1 if any differs. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--json`, `-j` | `boolean` | - | Output findings or metrics as JSON. |

## Commands

## `devops install-tools status`

**Show each tool's locked version and where its command is installed, without a request.**

```bash
devops install-tools status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--target-dir`, `-d` | `path` | `~/.local/bin` | Target directory path for operation. |

---
