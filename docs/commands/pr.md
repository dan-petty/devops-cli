# `devops pr`

GitHub Pull Request workflows and reviews.

## Commands

## `devops pr list`

**List pull requests with base targeting and review status.**

```bash
devops pr list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--state`, `-s` | `string` | `open` | Filter by state (open, closed, merged, all). |
| `--limit`, `-n` | `integer` | `30` | Maximum number of items to return or display. |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

---

## `devops pr view`

**View details of a pull request.**

```bash
devops pr view [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

---

## `devops pr checks`

**Check remote CI quality gate status on a pull request.**

```bash
devops pr checks [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

---

## `devops pr wait`

**Monitor PR checks, Copilot review sessions, and unresolved threads until ready.**

```bash
devops pr wait [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | No | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--interval`, `-i` | `integer` | `60` | Polling interval in seconds between check queries. |
| `--timeout`, `-t` | `integer` | `300` | Maximum time in seconds to wait for checks and reviews. |
| `--settle-timeout`, `-s` | `integer` | `60` | Grace period in seconds to allow Copilot review sessions to initialize. |
| `--require-reviews`, `--no-require-reviews` | `boolean` | `True` | Wait for active Copilot review sessions to conclude and check for unresolved threads. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

---

## `devops pr monitor`

**Monitor PR checks, Copilot review sessions, and unresolved threads until ready.**

```bash
devops pr monitor [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | No | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--interval`, `-i` | `integer` | `60` | Polling interval in seconds between check queries. |
| `--timeout`, `-t` | `integer` | `300` | Maximum time in seconds to wait for checks and reviews. |
| `--settle-timeout`, `-s` | `integer` | `60` | Grace period in seconds to allow Copilot review sessions to initialize. |
| `--require-reviews`, `--no-require-reviews` | `boolean` | `True` | Wait for active Copilot review sessions to conclude and check for unresolved threads. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

---

## `devops pr edit`

**Edit pull request base branch, title, or body.**

```bash
devops pr edit [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base`, `-B` | `string` | - | Change the base branch for this pull request. |
| `--title`, `-t` | `string` | - | Set the new title. |
| `--body`, `-b` | `string` | - | Set the new body. |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

---

## `devops pr create`

**Create a pull request with automatic release branch target validation.**

```bash
devops pr create [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--title`, `-t` | `string` | - | Title for the item or entity. |
| `--body`, `-b` | `string` | `` | Body or description text. |
| `--base`, `-B` | `string` | - | Base git branch to diff against (default: main). |
| `--draft`, `-d` | `boolean` | - | Create pull request or entity as draft. |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

---

## `devops pr threads`

```bash
devops pr threads COMMAND [ARGS]...
```

### `devops pr threads list`

**List PR review discussion threads, file locations, and comments.**

```bash
devops pr threads list [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |
| `--unresolved-only`, `-u` | `boolean` | - | Filter to display only unresolved review discussion threads. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |

### `devops pr threads reply`

**Post an in-thread reply to a PR review discussion thread.**

```bash
devops pr threads reply <thread_id> <body>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<thread_id>` | `string` | Yes | Review thread GraphQL ID (e.g. PRRT_...). |
| `<body>` | `string` | Yes | Reply message text to append directly to the review thread. |

### `devops pr threads resolve`

**Programmatically mark one or more PR review discussion threads as resolved.**

```bash
devops pr threads resolve <thread_ids>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<thread_ids>` | `string` | Yes | One or more review thread GraphQL IDs to resolve. |

### `devops pr threads unresolve`

**Reopen a previously resolved PR review discussion thread.**

```bash
devops pr threads unresolve <thread_id>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<thread_id>` | `string` | Yes | Review thread GraphQL ID (e.g. PRRT_...). |

---
