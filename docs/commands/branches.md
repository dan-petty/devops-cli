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
| `--base-dir`, `-d` | `path` | - | Base repository root directory. |

---

## `devops branches sync`

**Fetch and pull tracking branches across all repos.**

```bash
devops branches sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | Base repository root directory. |

---

## `devops branches jira`

**Create a feature branch for a Jira ticket: feature/PROJ-123[-slug].**

```bash
devops branches jira [OPTIONS] <ticket_id>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<ticket_id>` | `string` | Yes | Jira ticket ID, e.g. PROJ-123. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--slug`, `-s` | `string` | - | Short branch description. |
| `--repo`, `-r` | `path` | - | Repository root directory (default: current directory). |

---

## `devops branches list`

**List branches across all repos.**

```bash
devops branches list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | Base repository root directory. |
| `--all`, `-a` | `boolean` | - | Include remote branches. |

---

## `devops branches clean`

**Delete local branches merged into main/master.**

```bash
devops branches clean [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | Base repository root directory. |
| `--dry-run`, `-n` | `boolean` | - | Preview execution plan without mutating external state. |

---
