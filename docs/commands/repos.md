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

**List every worktree with commits ahead of main, dirty-path count, and flags.**

```bash
devops repos worktrees status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo-dir`, `-r` | `path` | - | Repository root directory. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--json` | `boolean` | - | Emit output as JSON. |

### `devops repos worktrees add`

**Create the worktree of an issue on \<type\>/\<issue\>-\<slug\> at the fetched origin/main.**

Create the worktree of an issue on \<type\>/\<issue\>-\<slug\> at the fetched origin/main.

The command first removes the worktrees of merged pull requests, as prune --confirm does,
because a merged worktree still holds its issue. Then it refuses an issue that a worktree,
the standard directory or a pushed branch of origin already holds. A pushed branch whose
commits past origin/main all have the App as author is a staged branch: the command adds the
worktree on it and takes --type and --slug from it. After the worktree exists, the command
claims the issue for an agent with the label owner/agent. It only warns if the claim fails.

```bash
devops repos worktrees add [OPTIONS] <issue>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<issue>` | `integer` | Yes | The number of the issue that the worktree is for. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--type` | `string` | - | The type of the branch: a type of release-please-config.json. Needed unless origin holds a staged branch for the issue; then it must equal the type of that branch. |
| `--slug` | `string` | - | The slug of the branch: lowercase letters and digits joined by single hyphens. Needed unless origin holds a staged branch for the issue; then it must equal the slug of that branch. |
| `--repo-dir`, `-r` | `path` | - | Repository root directory. |
| `--reclaim` / `--no-reclaim` | `boolean` | `True` | First remove the worktrees of merged pull requests, as prune --confirm does. --no-reclaim skips this. |
| `--dry-run`, `-n` | `boolean` | - | Preview execution plan without mutating external state. |
| `--format` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--json` | `boolean` | - | Emit output as JSON. |

### `devops repos worktrees prune`

**Remove the worktrees whose tip heads a merged pull request; preview unless --confirm.**

```bash
devops repos worktrees prune [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo-dir`, `-r` | `path` | - | Repository root directory. |
| `--force`, `-f` | `boolean` | - | Remove every worktree but the main one, whatever its state. Needs --confirm. |
| `--confirm` | `boolean` | - | Remove the worktrees. Without it, prune only lists what it would remove. |
| `--dry-run`, `-n` | `boolean` | - | Preview execution plan without mutating external state. |
| `--format` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--json` | `boolean` | - | Emit output as JSON. |

---
