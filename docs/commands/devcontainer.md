# `devops devcontainer`

Manage devcontainer configurations.

## Commands

## `devops devcontainer init`

**Scaffold .devcontainer/ in a repository using standard or published template.**

```bash
devops devcontainer init [OPTIONS] <repo_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<repo_path>` | `path` | No | Path to the repository |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--name`, `-n` | `string` | - | Project name |
| `--python` | `string` | `3.14` | Python version for base template |
| `--image`, `-i` | `string` | - | Base container image |
| `--published`, `-p` | `boolean` | - | Use published GHCR image (ghcr.io/dan-petty/devops-cli/devcontainer:latest) |

---

## `devops devcontainer update`

**Update the Python image version in an existing devcontainer.json.**

```bash
devops devcontainer update [OPTIONS] <repo_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<repo_path>` | `path` | No | Path to the repository |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--python` | `string` | `3.14` | - |

---

## `devops devcontainer validate`

**Validate .devcontainer/devcontainer.json manifest syntax and configuration schema.**

```bash
devops devcontainer validate [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--workspace`, `-w` | `path` | `.` | Path to workspace directory containing .devcontainer |
| `--config`, `-c` | `path` | - | Direct path to devcontainer.json |
| `--dry-run` | `boolean` | - | Simulate DevContainer manifest validation |

---

## `devops devcontainer list`

**List repos with their devcontainer status.**

```bash
devops devcontainer list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | - |

---

## `devops devcontainer post-create`

**Execute DevContainer post-create setup tasks (history, shell completions, config prep).**

```bash
devops devcontainer post-create [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--workspace`, `-w` | `path` | `.` | Path to workspace directory |
| `--dry-run` | `boolean` | - | Simulate execution without modifying files |

---

## `devops devcontainer post-start`

**Execute DevContainer post-start tasks (SSH keys, git defaults, kubeconfig, MCP sync).**

```bash
devops devcontainer post-start [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--workspace`, `-w` | `path` | `.` | Path to workspace directory |
| `--dry-run` | `boolean` | - | Simulate execution without modifying files |

---

## `devops devcontainer run-lifecycle`

**Run specified DevContainer lifecycle hook tasks natively in Python.**

```bash
devops devcontainer run-lifecycle [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--workspace`, `-w` | `path` | `.` | Path to workspace directory |
| `--post-create` | `boolean` | - | Execute post-create setup tasks |
| `--post-start` | `boolean` | - | Execute post-start lifecycle tasks |
| `--all`, `-a` | `boolean` | - | Execute all DevContainer lifecycle tasks |
| `--dry-run` | `boolean` | - | Simulate execution without modifying files |

---
