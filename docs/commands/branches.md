# `devops branches`

Branch management and Jira workflows.

## Commands

## `devops branches update`

**Fetch and pull tracking branches across all repos.**

```bash
devops branches update [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | - |

---

## `devops branches sync`

**Fetch and pull tracking branches across all repos.**

```bash
devops branches sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | - |

---

## `devops branches jira`

**Create a feature branch for a Jira ticket: feature/PROJ-123[-slug].**

```bash
devops branches jira [OPTIONS] <ticket_id>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<ticket_id>` | `string` | Yes | Jira ticket ID, e.g. PROJ-123 |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--slug`, `-s` | `string` | - | Short branch description |
| `--repo`, `-r` | `path` | - | Target repo (default: cwd) |

---

## `devops branches list`

**List branches across all repos.**

```bash
devops branches list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | - |
| `--all`, `-a` | `boolean` | - | Include remote branches |

---

## `devops branches create`

**Create a topic branch following repository branching standards.**

```bash
devops branches create [OPTIONS] <name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<name>` | `string` | Yes | Branch name or slug (e.g. mcp-tools-enhancement) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base`, `-b` | `string` | - | Base branch to fork from (defaults to active release branch) |
| `--type`, `-t` | `string` | `feat` | Branch type prefix (feat, fix, docs, chore, refactor) |
| `--repo`, `-r` | `path` | - | Target repo directory (default: cwd) |

---

## `devops branches status`

**Show detailed branch status, tracking state, ahead/behind drift, and worktree status.**

```bash
devops branches status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-r` | `path` | - | Target repo directory (default: cwd) |

---

## `devops branches clean`

**Delete local branches merged into main/master.**

```bash
devops branches clean [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | - |
| `--dry-run`, `-n` | `boolean` | - | Show what would be deleted |

---
