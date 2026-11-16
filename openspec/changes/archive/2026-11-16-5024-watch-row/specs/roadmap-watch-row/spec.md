## ADDED Requirements

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
`due_steps(state)` SHALL evaluate pull request states and return due lifecycle actions. It SHALL skip pull requests that have an active runner unit.

#### Scenario: Bot pull request is ready
- **WHEN** a bot pull request has all checks passing
- **THEN** `due_steps` returns the `ready` step

#### Scenario: Person pull request has a conflict
- **WHEN** a person pull request has merge conflicts with the default branch
- **THEN** `due_steps` returns the `comment_conflict` step

#### Scenario: Pull request is merged or closed
- **WHEN** a pull request is merged or closed
- **THEN** `due_steps` returns `status_sync` (and `cleanup` if it is a plan)

### Requirement: Dry run sends zero requests
In dry-run mode, the watch row SHALL send zero network requests.

#### Scenario: Dry-run execution
- **WHEN** `run_due_jobs` runs with `dry_run=True`
- **THEN** the watch row sends zero requests to GitHub
