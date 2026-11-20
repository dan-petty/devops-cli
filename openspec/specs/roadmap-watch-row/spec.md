# roadmap-watch-row Specification

## Purpose
Observe all open plan and delivery pull requests for a repository with batched GraphQL queries, back off repeated polling on failed heads, and route lifecycle actions through pure state evaluation.

## Requirements

### Requirement: The status lane runs the watch row
The status lane SHALL hold a row named `watch` that replaces `stage_ready` and `pr_conflicts`. The row SHALL need no clone, SHALL call no model, and SHALL be due on a first run and every `DEFAULT_ROADMAP_WATCH_INTERVAL_MINUTES` minutes.

#### Scenario: The status lane table holds watch
- **WHEN** the status lane table is read
- **THEN** it holds `watch` and neither `stage_ready` nor `pr_conflicts`, and `watch` needs no clone and is due on a first run

### Requirement: Watch reads open roadmap pull requests with one GraphQL query
The `watch` row SHALL query all open roadmap pull requests of a repository using one GraphQL query including `headRefOid`, `isDraft`, `mergeable`, and `statusCheckRollup`. When a GraphQL quota hold is active, it SHALL fall back to REST requests with conditional ETags.

#### Scenario: Open pull requests read via GraphQL
- **WHEN** the watch row executes a round for a repository with open pull requests
- **THEN** it issues one GraphQL request to retrieve open pull request details and check runs

### Requirement: Watch maintains a ledger with failed head backoff
The watch row SHALL keep a ledger recording the pull request number, head SHA, verdict, and next read time. It SHALL NOT re-read checks for a failed head within 30 minutes unless the head commit or base branch moves.

#### Scenario: Failed head is not re-read within 30 minutes
- **WHEN** a pull request head has failed checks and 10 minutes have elapsed
- **THEN** the row skips re-reading the checks and keeps the existing verdict

#### Scenario: Head change clears the backoff
- **WHEN** a new commit is pushed to a previously failed pull request
- **THEN** the row reads the new head immediately

### Requirement: The due_steps pure function routes pull request states
`due_steps(state)` SHALL evaluate pull request states and return due lifecycle actions. It SHALL skip a pull request whose item has a live unit: a runner Job that no round reported, or the check-out of a stage Job. A FAILED bot pull request whose failed check has the class test, lint, types or plan check SHALL get `fix_checks`, with the check that holds the cause; a `ci_infra` failure and a cancelled check SHALL get no `fix_checks`.

#### Scenario: Bot pull request is ready
- **WHEN** a bot pull request has all checks passing
- **THEN** `due_steps` returns the `ready` step

#### Scenario: Person pull request has a conflict
- **WHEN** a person pull request has merge conflicts with the default branch
- **THEN** `due_steps` returns the `comment_conflict` step

#### Scenario: Pull request is merged or closed
- **WHEN** a pull request is merged or closed
- **THEN** `due_steps` returns `status_sync` (and `cleanup` if it is a plan)

#### Scenario: A bot pull request with a failed test check
- **WHEN** a bot pull request has a failed `Tests & Coverage (shard 2)` check and a failed `Tests & Coverage` check
- **THEN** `due_steps` returns `fix_checks`, and the check of the unit is the shard

#### Scenario: A failed title check gets no fix unit
- **WHEN** a bot pull request has a failed `Semantic PR title` check
- **THEN** `due_steps` returns `comment_ci_infra` and no `fix_checks`

### Requirement: Dry run sends zero requests
In dry-run mode, the watch row SHALL send zero network requests.

#### Scenario: Dry-run execution
- **WHEN** `run_due_jobs` runs with `dry_run=True`
- **THEN** the watch row sends zero requests to GitHub

### Requirement: An error of the fix-checks round does not stop the watch row
When the fix-checks round raises a Kubernetes error, such as `ClusterJobError`, or a `ConfigurationError`, the watch row SHALL log it, count it in `devops_cli_service_fix_checks_jobs_total` with the result `round_error`, keep its ledger, and give its result with an empty fix-checks round.

#### Scenario: A missing CronJob
- **WHEN** a bot pull request is due for a fix and CronJob `devops-cli-runner` is missing
- **THEN** the row logs and counts `round_error`, writes its ledger, and gives its result

#### Scenario: Limits that do not nest
- **WHEN** a bot pull request is due for a fix and `roadmap.implement.step_time_limit_seconds` gives a deadline above the cap
- **THEN** the row logs and counts `round_error`, writes its ledger, and gives its result

### Requirement: The watch row marks a plan draft ready only when draft readiness allows it
For a green bot draft that an item records as `stage.pr`, the watch row SHALL read the draft with `read_ready_draft` and SHALL mark it ready only when `draft_readiness` answers ready. The kind of the draft SHALL come from the record, so a pull request that the item records as `stage.pr` and as `implement.pr` is judged as its delivery. The row SHALL keep a refused head in the ledger field `ready_head` and SHALL judge that head once.

#### Scenario: A delivery on the plan branch with an unticked task group
- **WHEN** an item records one green draft as `stage.pr` and as `implement.pr`, and task group 5 of its change has a task that is not ticked
- **THEN** two rounds of the row send no `gh pr ready` and record no `stage.ready`

#### Scenario: A green plan draft that the decision allows
- **WHEN** an item records a green bot draft as `stage.pr` and `draft_readiness` answers ready
- **THEN** the row marks it ready and records `stage.ready`

### Requirement: A pull request holds one conflict comment
The `comment_conflict` step SHALL keep one conflict comment on a pull request. The marker `<!-- devops roadmap pr_conflicts -->` SHALL be the only key of the comment. When the pull request holds a comment with the marker, the step SHALL edit that comment in place with the text of the current head, and SHALL post no second comment. The step SHALL post a comment only when no comment of the pull request holds the marker.

#### Scenario: The first conflict
- **WHEN** a person pull request that holds no conflict comment has a merge conflict
- **THEN** the row posts one conflict comment that names the base branch and the head commit

#### Scenario: A conflict at a new head
- **WHEN** the pull request holds the conflict comment of an older head and has a conflict at a new head
- **THEN** the row edits that comment with the new head and posts no comment

### Requirement: The watch row marks a delivery draft ready after a fix or a drafted end
For a delivery draft with the verdict READY, the watch row SHALL run the ready path of the step `fix-checks` only when its item records `fix_checks.result` as `repaired` or `implement.result` as `drafted`, once for each head, with `--confirm` only in mode `on` of `roadmap.fix_checks.mode`, and SHALL ask the step for its ready path only. The row SHALL leave each other delivery draft, such as the draft of a stopped implement Job, and SHALL send it no request.

#### Scenario: A repaired draft gets the ready path once
- **WHEN** a delivery draft that a fix Job repaired has passing checks, and the row runs twice on its head in mode `plan`
- **THEN** the row runs the ready path once, with no `--confirm` and with `ready_only`

#### Scenario: A drafted end gets the ready path once
- **WHEN** a delivery draft whose implement Job recorded `implement.result` equal to `drafted` has passing checks, and the row runs twice on its head in mode `plan`
- **THEN** the row runs the ready path once, with no `--confirm` and with `ready_only`

#### Scenario: A draft of a stopped Job is left alone
- **WHEN** a delivery draft whose implement Job recorded `implement.result` equal to `stopped` has passing checks and no `fix_checks.result`
- **THEN** the row runs no ready path and sends GitHub only its GraphQL read
