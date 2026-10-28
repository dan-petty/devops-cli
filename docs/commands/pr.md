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

**Wait until the checks of a PR settle, then name every blocker of its merge.**

Wait until the checks of a PR settle, then name every blocker of its merge.

While a check runs or a Copilot review is active, it waits. Then it reports the blockers of
the merge-readiness verdict and of its review gate (requested changes, Copilot's review, an
approval of the head with --require-reviews). Exit 0: ready; 1: a check failed or could not
be read; 2: another blocker; 3: the timeout passed first.

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
| `--require-reviews` / `--no-require-reviews` | `boolean` | `True` | Wait for active Copilot review sessions to conclude and check for unresolved threads. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

---

## `devops pr monitor`

**Wait until the checks of a PR settle, then name every blocker of its merge.**

Wait until the checks of a PR settle, then name every blocker of its merge.

While a check runs or a Copilot review is active, it waits. Then it reports the blockers of
the merge-readiness verdict and of its review gate (requested changes, Copilot's review, an
approval of the head with --require-reviews). Exit 0: ready; 1: a check failed or could not
be read; 2: another blocker; 3: the timeout passed first.

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
| `--require-reviews` / `--no-require-reviews` | `boolean` | `True` | Wait for active Copilot review sessions to conclude and check for unresolved threads. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

---

## `devops pr edit`

**Edit pull request base branch, title, body, or milestone.**

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
| `--milestone`, `-m` | `string` | - | Set the milestone for this pull request. |

---

## `devops pr create`

**Open a draft pull request, into the default branch unless --base names another.**

Open a draft pull request, into the default branch unless --base names another.

Every pull request opens as a draft. devops pr ready is the only way to mark it ready for
review.

```bash
devops pr create [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--title`, `-t` | `string` | - | Title for the item or entity. |
| `--body`, `-b` | `string` | `` | Body or description text. |
| `--base`, `-B` | `string` | - | Base branch of the pull request; the repository's default branch when omitted. |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

---

## `devops pr ready`

**Mark a draft pull request as ready for review once its checks pass.**

Mark a draft pull request as ready for review once its checks pass.

It exits 1 when a check failed or could not be read and 8 while one runs. Every other
blocker of the merge-readiness verdict prints as a warning. --force skips the checks.

```bash
devops pr ready [OPTIONS] <number>
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

---

## `devops pr diff`

**View diff of a pull request.**

```bash
devops pr diff [OPTIONS] <number>
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

---

## `devops pr close`

**Close a pull request.**

```bash
devops pr close [OPTIONS] <number>
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

---

## `devops pr check-readiness`

**Validate PR merge readiness: conflicts, draft state, checks, review threads and grounding.**

Validate PR merge readiness: conflicts, draft state, checks, review threads and grounding.

Grounding applies where the base holds openspec/changes/. The PR targets the default branch.
It closes exactly one issue, an open issue of its own repository that holds a priority/*
label: a roadmap item. GitHub closes that issue when the PR merges. The PR
adds openspec/changes/archive/\<date\>-\<issue\>-\<slug\>/, which uv run devops openspec archive
writes for that issue's change. Only that archive writes openspec/specs/ and
openspec/changes/archive/.

```bash
devops pr check-readiness [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | No | PR number to verify (defaults to current branch PR) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--allow-draft` | `boolean` | - | Report a draft pull request as ready; GitHub still refuses to merge one. |
| `--allow-pending-checks` | `boolean` | - | Treat checks that are still running as acceptable rather than blocking. |
| `--allow-blocked-state` | `boolean` | - | Allow mergeable_state 'blocked' (e.g. when executing within CI while checks/approvals are pending) |
| `--auto-resolve` | `boolean` | - | Automatically resolve review discussion threads that have received a reply from someone other than the thread opener. |
| `--allow-replied-threads` | `boolean` | - | Treat review discussion threads that have received a reply from someone other than the thread opener as addressed rather than blocking. |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

---

## `devops pr update`

**Update pull request branch with latest commits from its base branch.**

```bash
devops pr update [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | No | Pull request number to update (optional if --all is specified). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--all`, `-a` | `boolean` | - | Update every open pull request that the current account wrote. |
| `--base`, `-B` | `string` | - | With --all, update only the pull requests into this base branch. |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |
| `--expected-head-sha` | `string` | - | Expected SHA of the pull request's HEAD ref for optimistic locking. |
| `--dispatch-ci` | `boolean` | - | Dispatch the ci.yml workflow on the head branch after updating. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops pr hardening-report`

**Audit merged defect pull requests for guardrail additions to declared hardening surfaces.**

```bash
devops pr hardening-report [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--pr` | `integer` | - | Audit a specific pull request by number. |
| `--fail-on-missing` | `boolean` | - | Exit with non-zero exit code if hardening is missing on any audited defect pull request. |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |
| `--limit`, `-n` | `integer` | `100` | Maximum number of merged PRs to inspect |
| `--format`, `-f` | `string` | `table` | Output format (table, json) |

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
devops pr threads resolve [OPTIONS] <thread_ids>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<thread_ids>` | `string` | Yes | One or more review thread GraphQL IDs to resolve. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--without-reply`, `-w` | `boolean` | - | Force resolution of review threads even if they lack a reply from someone other than the thread opener. |

### `devops pr threads unresolve`

**Reopen a previously resolved PR review discussion thread.**

```bash
devops pr threads unresolve <thread_id>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<thread_id>` | `string` | Yes | Review thread GraphQL ID (e.g. PRRT_...). |

### `devops pr threads resolve-all`

**Resolve all or replied review discussion threads for a pull request.**

```bash
devops pr threads resolve-all [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--only-replied` / `--all` | `boolean` | `True` | Only resolve threads that have received a reply from someone other than the thread opener. |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

---
