# `devops workspace`

Manage VS Code workspace files.

## Commands

## `devops workspace add`

**Add a folder to the VS Code workspace file.**

```bash
devops workspace add [OPTIONS] <repo_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<repo_path>` | `path` | Yes | Folder path to add |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--workspace`, `-w` | `path` | - | - |

---

## `devops workspace remove`

**Remove a folder from the VS Code workspace file.**

```bash
devops workspace remove [OPTIONS] <repo_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<repo_path>` | `path` | Yes | Remove a repository folder from the VS Code workspace file. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--workspace`, `-w` | `path` | - | - |

---

## `devops workspace generate`

**Regenerate the workspace file from all repos in the repos directory.**

```bash
devops workspace generate [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | - |
| `--workspace`, `-w` | `path` | - | - |

---

## `devops workspace open`

**Open the workspace in VS Code.**

```bash
devops workspace open [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--workspace`, `-w` | `path` | - | - |

---

## `devops workspace clean`

**Clean stale review sessions, old analysis caches, and temporary traces under .data/.**

```bash
devops workspace clean [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--older-than`, `-d` | `integer` | `7` | Prune artifacts older than N days |
| `--dry-run` | `boolean` | - | Simulate pruning without deleting files |

---
