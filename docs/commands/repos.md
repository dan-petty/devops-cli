# `devops repos`

Clone, synchronize, and manage organization repositories.

## Commands

## `devops repos clone-org`

**Clone all repos from a GitHub org into `repos/<org>/.`.**

```bash
devops repos clone-org [OPTIONS] <org>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<org>` | `string` | No | GitHub organisation name. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | Base repository root directory. |
| `--private` / `--no-private` | `boolean` | `True` | - |
| `--forks` / `--no-forks` | `boolean` | - | - |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops repos clone`

**Clone an individual repository into `repos/<org>/<name>/.` (or `repos/_standalone/<name>/.`).**

```bash
devops repos clone [OPTIONS] <url>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<url>` | `string` | Yes | Repository URL (SSH or HTTPS). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | Base repository root directory. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops repos list`

**List all cloned repositories.**

```bash
devops repos list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | - |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops repos update`

**Fetch (and optionally pull) all tracking branches across repos.**

```bash
devops repos update [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | - |
| `--pull` / `--no-pull` | `boolean` | `True` | - |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops repos sync`

**Fetch (and optionally pull) all tracking branches across repos.**

```bash
devops repos sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | - |
| `--pull` / `--no-pull` | `boolean` | `True` | - |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops repos worktrees`

```bash
devops repos worktrees COMMAND [ARGS]...
```

### `devops repos worktrees status`

**List every worktree with commits ahead of main, dirty-path count, contained status, and flags.**

```bash
devops repos worktrees status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo-dir`, `-r` | `path` | - | Repository root directory. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--json` | `boolean` | - | Emit output as JSON. |

### `devops repos worktrees prune`

**Safely prune orphan git worktrees, dry-run by default.**

```bash
devops repos worktrees prune [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo-dir`, `-r` | `path` | - | Repository root directory. |
| `--force`, `-f` | `boolean` | - | Remove entries regardless of clean or contained status. |
| `--dry-run`, `-n` | `boolean` | - | Preview execution plan without mutating external state. |
| `--format` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--json` | `boolean` | - | Emit output as JSON. |

---
