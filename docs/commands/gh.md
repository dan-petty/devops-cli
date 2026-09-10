# `devops gh`

GitHub Views, Projects, Issues, Pages, Milestones, and Labels automation.

## Commands

## `devops gh labels`

```bash
devops gh labels COMMAND [ARGS]...
```

### `devops gh labels list`

**List all labels defined in the remote repository.**

```bash
devops gh labels list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |

### `devops gh labels sync`

**Synchronize repository labels against the declarative YAML schema.**

```bash
devops gh labels sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--file`, `-f` | `path` | `.github/labels.yml` | Path to declarative labels.yml file |
| `--repo`, `-R` | `string` | - | Target repository |
| `--dry-run` | `boolean` | - | Preview label reconciliation without making changes |

### `devops gh labels audit`

**Audit open pull requests for mandatory type/ and scope/ taxonomy labels.**

```bash
devops gh labels audit [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |

---

## `devops gh milestones`

```bash
devops gh milestones COMMAND [ARGS]...
```

### `devops gh milestones list`

**List repository milestones and track issue completion rates.**

```bash
devops gh milestones list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--state`, `-s` | `string` | `all` | Milestone state filter |
| `--repo`, `-R` | `string` | - | Target repository |

### `devops gh milestones sync`

**Extract release milestones from ROADMAP.md and sync to repository.**

```bash
devops gh milestones sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--roadmap`, `-r` | `path` | `docs/ROADMAP.md` | Path to docs/ROADMAP.md file |
| `--repo`, `-R` | `string` | - | Target repository |
| `--dry-run` | `boolean` | - | Simulate milestone extraction without creating remote records |

### `devops gh milestones status`

**Inspect detailed progress and issue health for a specific milestone.**

```bash
devops gh milestones status [OPTIONS] <name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<name>` | `string` | Yes | Milestone version or title (e.g. v0.2.11) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |

### `devops gh milestones close`

**Close a repository release milestone by title or version.**

```bash
devops gh milestones close [OPTIONS] <name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<name>` | `string` | Yes | Milestone version or title (e.g. v0.2.11) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |

---

## `devops gh project`

```bash
devops gh project COMMAND [ARGS]...
```

### `devops gh project status`

**Inspect the declarative GitHub Projects v2 template structure and views.**

```bash
devops gh project status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--template`, `-t` | `path` | `.github/project-template.json` | Path to project template JSON |

### `devops gh project sync`

**Sync task items from task.md into GitHub Projects status.**

```bash
devops gh project sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--task-file`, `-f` | `path` | `docs/agent/task.md` | Path to docs/agent/task.md |
| `--template`, `-t` | `path` | `.github/project-template.json` | Path to project template JSON |
| `--repo`, `-R` | `string` | - | Target repository |
| `--dry-run`, `--no-dry-run` | `boolean` | - | Preview task card items without remote mutations |
| `--reconcile-fields`, `--no-reconcile-fields` | `boolean` | `True` | Automatically infer and update project custom fields from taxonomy labels and issue state. |

### `devops gh project reconcile`

**Reconcile custom fields (Status, Priority, Category, Value, Effort) on project items.**

```bash
devops gh project reconcile [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--project-number`, `-n` | `integer` | - | GitHub Projects v2 board number |
| `--repo`, `-R` | `string` | - | Target repository |
| `--dry-run` | `boolean` | - | Preview field reconciliation without mutations |

### `devops gh project link`

**Link a GitHub Project v2 board to the repository.**

```bash
devops gh project link [OPTIONS] <project_number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<project_number>` | `integer` | Yes | GitHub Projects v2 board number |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |

### `devops gh project list`

**List available GitHub Projects v2 boards for user or organization.**

```bash
devops gh project list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--owner`, `-o` | `string` | - | Target user or organization |

### `devops gh project audit`

**Audit project board items and fields against local tasks and template.**

```bash
devops gh project audit [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--template`, `-t` | `path` | `.github/project-template.json` | Path to project template JSON |
| `--repo`, `-R` | `string` | - | Target repository |

### `devops gh project template`

**Display the raw GitHub Projects v2 declarative JSON template.**

```bash
devops gh project template [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--template`, `-t` | `path` | `.github/project-template.json` | Path to project template JSON |

---

## `devops gh views`

```bash
devops gh views COMMAND [ARGS]...
```

### `devops gh views list`

**List all standardized GitHub Projects v2 views configured for this workspace.**

```bash
devops gh views list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--template`, `-t` | `path` | `.github/project-template.json` | Path to project template JSON |

### `devops gh views spec`

**Output JSON schema specification for all configured project views.**

```bash
devops gh views spec [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--template`, `-t` | `path` | `.github/project-template.json` | Path to project template JSON |

### `devops gh views sync`

**Synchronize standardized views with the remote GitHub Projects v2 board.**

```bash
devops gh views sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--template`, `-t` | `path` | `.github/project-template.json` | Path to project template JSON |
| `--repo`, `-R` | `string` | - | Target repository |

### `devops gh views audit`

**Audit remote project views against standardized template specifications.**

```bash
devops gh views audit [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--template`, `-t` | `path` | `.github/project-template.json` | Path to project template JSON |
| `--repo`, `-R` | `string` | - | Target repository |

---

## `devops gh pages`

```bash
devops gh pages COMMAND [ARGS]...
```

### `devops gh pages status`

**Inspect GitHub Pages deployment status, URL, branch, and HTTPS enforcement.**

```bash
devops gh pages status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |

### `devops gh pages builds`

**List recent GitHub Pages build history and durations.**

```bash
devops gh pages builds [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |
| `--limit`, `-l` | `integer` | `5` | Number of builds to retrieve |

### `devops gh pages build`

**Trigger a new deployment build for GitHub Pages.**

```bash
devops gh pages build [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |

### `devops gh pages verify`

**Verify local repository readiness for GitHub Pages publishing.**

```bash
devops gh pages verify [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dir`, `-d` | `path` | `.` | Path to project root directory |

---

## `devops gh issues`

```bash
devops gh issues COMMAND [ARGS]...
```

### `devops gh issues list`

**List repository issues with milestone, taxonomy labels, and status.**

```bash
devops gh issues list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |
| `--state`, `-s` | `string` | `open` | Issue state: open, closed, all |
| `--milestone`, `-m` | `string` | - | Filter by milestone |
| `--label`, `-l` | `string` | - | Filter by label |
| `--limit` | `integer` | `30` | Max issues to return |

### `devops gh issues create`

**Create a new issue linking milestone and taxonomy labels.**

```bash
devops gh issues create [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--title`, `-t` | `string` | - | Issue title |
| `--body`, `-b` | `string` | `` | Issue description |
| `--milestone`, `-m` | `string` | - | Target milestone |
| `--label`, `-l` | `string` | - | Taxonomy label (repeatable) |
| `--repo`, `-R` | `string` | - | Target repository |

### `devops gh issues triage`

**Audit open issues for mandatory taxonomy labels and milestone linkage.**

```bash
devops gh issues triage [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |

### `devops gh issues status`

**Display aggregated issue counts by priority, type, and milestone.**

```bash
devops gh issues status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |

---

## `devops gh pr`

```bash
devops gh pr COMMAND [ARGS]...
```

### `devops gh pr list`

**List pull requests with base targeting and review status.**

```bash
devops gh pr list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--state`, `-s` | `string` | `open` | Filter by state (open, closed, merged, all). |
| `--limit`, `-n` | `integer` | `30` | Maximum number of items to return or display. |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

### `devops gh pr view`

**View details of a pull request.**

```bash
devops gh pr view [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

### `devops gh pr checks`

**Check remote CI quality gate status on a pull request.**

```bash
devops gh pr checks [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

### `devops gh pr edit`

**Edit pull request base branch, title, or body.**

```bash
devops gh pr edit [OPTIONS] <number>
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

### `devops gh pr create`

**Create a pull request with automatic release branch target validation.**

```bash
devops gh pr create [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--title`, `-t` | `string` | - | Title for the item or entity. |
| `--body`, `-b` | `string` | `` | Body or description text. |
| `--base`, `-B` | `string` | - | Base git branch to diff against (default: main). |
| `--draft`, `-d` | `boolean` | - | Create pull request or entity as draft. |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

### `devops gh pr threads`

```bash
devops gh pr threads COMMAND [ARGS]...
```

#### `devops gh pr threads list`

**List PR review discussion threads, file locations, and comments.**

```bash
devops gh pr threads list [OPTIONS] <number>
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

#### `devops gh pr threads reply`

**Post an in-thread reply to a PR review discussion thread.**

```bash
devops gh pr threads reply <thread_id> <body>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<thread_id>` | `string` | Yes | Review thread GraphQL ID (e.g. PRRT_...). |
| `<body>` | `string` | Yes | Reply message text to append directly to the review thread. |

#### `devops gh pr threads resolve`

**Programmatically mark one or more PR review discussion threads as resolved.**

```bash
devops gh pr threads resolve <thread_ids>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<thread_ids>` | `string` | Yes | One or more review thread GraphQL IDs to resolve. |

#### `devops gh pr threads unresolve`

**Reopen a previously resolved PR review discussion thread.**

```bash
devops gh pr threads unresolve <thread_id>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<thread_id>` | `string` | Yes | Review thread GraphQL ID (e.g. PRRT_...). |

---
