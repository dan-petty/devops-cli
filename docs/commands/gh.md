# `devops gh`

GitHub Views, Projects, Issues, Pages, Milestones, and Labels automation.

## Commands

## `devops gh api`

**Execute a GitHub API request with token-bucket pacing, rate-limit backoff, and optional caching.**

```bash
devops gh api [OPTIONS] <endpoint>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<endpoint>` | `string` | Yes | GitHub API endpoint (e.g. repos/:owner/:repo/issues) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--method`, `-X` | `string` | - | HTTP method (GET, POST, PUT, DELETE, PATCH) |
| `--paginate` | `boolean` | - | Paginate across all result pages |
| `--jq`, `-q` | `string` | - | Filter JSON output using a jq expression |
| `--template`, `-t` | `string` | - | Format JSON output using a Go template |
| `--cache` | `boolean` | - | Cache response in-memory for subsequent reads |
| `--cache-ttl` | `float` | `15.0` | Cache TTL in seconds (default 15.0) |

---

## `devops gh rate-limit`

**Display GitHub REST and GraphQL API rate limits, quotas, and reset countdowns.**

```bash
devops gh rate-limit [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |

---

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

**Sync task items from docs/agent/tasks directory into GitHub Projects status.**

```bash
devops gh project sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--task-file`, `-f` | `path` | `docs/agent/tasks` | Path to docs/agent/tasks directory |
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

### `devops gh issues edit`

**Edit an existing issue title, body, or state.**

```bash
devops gh issues edit [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Issue number to edit. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--title`, `-t` | `string` | - | New issue title. |
| `--body`, `-b` | `string` | - | New issue body text. |
| `--state`, `-s` | `string` | - | New state (open or closed). |
| `--repo`, `-R` | `string` | - | Target repository |

### `devops gh issues sync-roadmap`

**Synchronize uncompleted roadmap deliverables into GitHub Issues and per-task tracking files.**

```bash
devops gh issues sync-roadmap [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--milestone`, `-m` | `string` | - | Filter by release milestone (e.g. v0.2.20) |
| `--dry-run` | `boolean` | - | Preview issue and task creation without modifying remote state |
| `--limit`, `-L` | `integer` | `20` | Maximum issues to create |
| `--repo`, `-R` | `string` | - | Target repository |

---

## `devops gh runs`

```bash
devops gh runs COMMAND [ARGS]...
```

### `devops gh runs list`

**List recent workflow runs for the repository or branch.**

```bash
devops gh runs list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--limit`, `-n` | `integer` | `10` | Maximum number of items to return or display. |
| `--branch`, `-b` | `string` | - | Filter by branch |
| `--repo`, `-R` | `string` | - | Target repository |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |

### `devops gh runs view`

**View details and failure logs of a specific workflow run.**

```bash
devops gh runs view [OPTIONS] <run_id>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<run_id>` | `integer` | Yes | Workflow run database ID. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--log-failed` | `boolean` | - | Display logs for failed jobs or steps in the workflow run. |
| `--log` | `boolean` | - | Display full execution logs for the workflow run. |
| `--job`, `-j` | `string` | - | Filter workflow run logs to a specific job ID. |
| `--repo`, `-R` | `string` | - | Target repository |

---

## `devops gh branch-protection`

```bash
devops gh branch-protection COMMAND [ARGS]...
```

### `devops gh branch-protection audit`

**Audit repository branch protection rulesets against declarative policy specification.**

```bash
devops gh branch-protection audit [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |
| `--branch`, `-b` | `string` | - | Target specific branch for protection audit or synchronization. |
| `--policy-file`, `-f` | `path` | `.github/branch-protection.yml` | Path to declarative branch protection policy YAML file. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

### `devops gh branch-protection sync`

**Synchronize repository branch protection rulesets against declarative policy specification.**

```bash
devops gh branch-protection sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |
| `--branch`, `-b` | `string` | - | Target specific branch for protection audit or synchronization. |
| `--policy-file`, `-f` | `path` | `.github/branch-protection.yml` | Path to declarative branch protection policy YAML file. |
| `--dry-run` | `boolean` | - | Preview branch protection synchronization without applying mutations |

---

## `devops gh secrets`

```bash
devops gh secrets COMMAND [ARGS]...
```

### `devops gh secrets sync`

**Synchronize repository secrets from OS Keyring or HashiCorp Vault with libsodium sealing.**

```bash
devops gh secrets sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--secret-names`, `-n` | `string` | - | Comma-separated list of secret names to synchronize. |
| `--repo`, `-R` | `string` | - | Target repository |
| `--source`, `-s` | `string` | `keyring` | Source store for secrets to synchronize (keyring or vault). |
| `--vault-path` | `string` | `secret/devops` | Vault KV-v2 secret path when source is vault (default: secret/devops). |
| `--dry-run` | `boolean` | - | Preview secret synchronization without mutations |

### `devops gh secrets list`

**List Actions secrets configured in the repository (names only, values are hidden).**

```bash
devops gh secrets list [OPTIONS]
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

### `devops gh pr wait`

**Monitor PR checks, Copilot review sessions, and unresolved threads until ready.**

```bash
devops gh pr wait [OPTIONS] <number>
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

### `devops gh pr monitor`

**Monitor PR checks, Copilot review sessions, and unresolved threads until ready.**

```bash
devops gh pr monitor [OPTIONS] <number>
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

### `devops gh pr edit`

**Edit pull request base branch, title, body, or milestone.**

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
| `--milestone`, `-m` | `string` | - | Set the milestone for this pull request. |

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

### `devops gh pr ready`

**Mark a draft pull request as ready for review.**

```bash
devops gh pr ready [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |
| `--monitor`, `-m` | `boolean` | - | Automatically transition to monitoring checks and reviews after marking ready. |
| `--force`, `-f` | `boolean` | - | Bypass failing check verification and force ready status |

### `devops gh pr diff`

**View diff of a pull request.**

```bash
devops gh pr diff [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |
| `--color` | `string` | `auto` | Whether to colorize diff (always, never, auto). |

### `devops gh pr close`

**Close a pull request.**

```bash
devops gh pr close [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--comment`, `-c` | `string` | - | Comment text to include when closing the pull request. |
| `--delete-branch`, `-d` | `boolean` | - | Delete remote topic branch upon closing. |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

### `devops gh pr check-readiness`

**Validate PR merge readiness: verify no unresolved review threads, no conflicts, and clean state.**

```bash
devops gh pr check-readiness [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | No | PR number to verify (defaults to current branch PR) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--require-ready` | `boolean` | - | Fail if the pull request is in draft status |
| `--allow-blocked-state` | `boolean` | - | Allow mergeable_state 'blocked' (e.g. when executing within CI while checks/approvals are pending) |
| `--auto-resolve` | `boolean` | - | Automatically resolve review discussion threads that have received replies. |
| `--allow-replied-threads` | `boolean` | - | Treat review discussion threads that have received replies as addressed rather than blocking. |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

### `devops gh pr update`

**Update pull request branch with latest commits from its base branch.**

```bash
devops gh pr update [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | No | Pull request number to update (optional if --all is specified). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--all`, `-a` | `boolean` | - | Update all open pull requests targeting the base branch. |
| `--base`, `-B` | `string` | - | Filter open pull requests by base branch (e.g. main, release/v0.2.20). |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |
| `--expected-head-sha` | `string` | - | Expected SHA of the pull request's HEAD ref for optimistic locking. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

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

#### `devops gh pr threads resolve-all`

**Resolve all or replied review discussion threads for a pull request.**

```bash
devops gh pr threads resolve-all [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--only-replied`, `--all` | `boolean` | `True` | Only resolve threads that have received one or more in-thread replies. |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

---
