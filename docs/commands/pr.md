# `devops pr`

Manage GitHub pull requests and base branch targeting.

## Commands

## `devops pr list`

**List pull requests with base targeting and review status.**

```bash
devops pr list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--state`, `-s` | `string` | `open` | Filter by state (open, closed, merged, all) |
| `--limit`, `-n` | `integer` | `10` | Maximum number of pull requests to display |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format |

---

## `devops pr view`

**View details of a pull request.**

```bash
devops pr view [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format |

---

## `devops pr checks`

**Check remote CI quality gate status on a pull request.**

```bash
devops pr checks [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format |

---

## `devops pr edit`

**Edit pull request base branch, title, or body.**

```bash
devops pr edit [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base`, `-B` | `string` | - | Change the base branch for this pull request |
| `--title`, `-t` | `string` | - | Set the new title |
| `--body`, `-b` | `string` | - | Set the new body |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format |

---

## `devops pr create`

**Create a pull request with automatic release branch target validation.**

```bash
devops pr create [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--title`, `-t` | `string` | - | Pull request title |
| `--body`, `-b` | `string` | `` | Pull request body text |
| `--base`, `-B` | `string` | - | Target base branch (defaults to active release branch) |
| `--draft`, `-d` | `boolean` | - | Create pull request as draft |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format |

---
