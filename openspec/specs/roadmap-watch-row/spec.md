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
A round of the `watch` row with no delivered pull request number SHALL query all open roadmap pull requests of a repository using one GraphQL query including `headRefOid`, `isDraft`, `mergeable`, and `statusCheckRollup`. When a GraphQL quota hold is active, it SHALL fall back to REST requests with conditional ETags.

#### Scenario: Open pull requests read via GraphQL
- **WHEN** the watch row executes a round with no delivered pull request number for a repository with open pull requests
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
`due_steps(state)` SHALL return the due lifecycle actions of a pull request, and none for an item with a live unit. A FAILED bot pull request whose failed check has the class test, lint, types or plan check SHALL get `fix_checks`, but a delivery draft only when a unit owns the check (`repair_owner`). A delivery draft whose failed or cancelled check no unit owns, or whose verdict is CONFLICT, SHALL get `stop`; another bot pull request SHALL get no `stop`.

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
- **WHEN** a delivery draft has a failed `Semantic PR title` check
- **THEN** `due_steps` returns `stop` and no `fix_checks`

#### Scenario: A cancelled check of a delivery draft
- **WHEN** the `Tests & Coverage` check of a delivery draft is cancelled
- **THEN** `due_steps` returns `stop`

#### Scenario: A delivery draft whose unit ended
- **WHEN** a delivery draft in mode `on` has a failed `Tests & Coverage` check whose unit ended with no repair
- **THEN** `due_steps` returns `stop` and no `fix_checks`

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
For a delivery draft with the verdict READY whose item holds no stop and records `fix_checks.result` as `repaired` or `rebased`, or `implement.result` as `drafted`, the watch row SHALL run only the ready path of the step `fix-checks`, once for each head that it reported on, with `--confirm` only in mode `on` of `roadmap.fix_checks.mode`. A Staged item that delivers on its plan pull request SHALL get the same guards on the plan path. The row SHALL send no request for each other delivery draft.

#### Scenario: A repaired draft gets the ready path once
- **WHEN** a delivery draft that a fix Job repaired has passing checks, and the row runs twice on its head in mode `plan`
- **THEN** the row runs the ready path once, with no `--confirm` and with `ready_only`

#### Scenario: A drafted end gets the ready path once
- **WHEN** a delivery draft whose implement Job recorded `implement.result` equal to `drafted` has passing checks, and the row runs twice on its head in mode `plan`
- **THEN** the row runs the ready path once, with no `--confirm` and with `ready_only`

#### Scenario: A draft of a stopped Job is left alone
- **WHEN** a delivery draft whose implement Job recorded `implement.result` equal to `stopped` has passing checks and no `fix_checks.result`
- **THEN** the row runs no ready path and sends GitHub only its GraphQL read

#### Scenario: A ready path that raises
- **WHEN** the ready path raises a GitHub error in the first round, and the row runs again on the same head
- **THEN** the row runs the ready path again

#### Scenario: A Staged delivery outside mode on
- **WHEN** a green drafted delivery draft is also the plan pull request of its item, in mode `plan` or `off`, or with an owner label
- **THEN** the row reads no draft and marks nothing ready

### Requirement: The pull request of a stopped item gets no fix unit
The watch row SHALL give no `fix_checks` to the pull request that the record of an item names as `implement.pr` while the item holds `implement.stopped`. A person owns the item until `implement: retry` clears the stop, and the ready path leaves the draft too.

#### Scenario: A new head after a stop
- **WHEN** the row stopped the item, and a new head of its draft has a failed `Tests & Coverage` check in mode `on`
- **THEN** the row hands no unit to the fix round, and the item stays Blocked

### Requirement: The watch row stops the item of a delivery draft that no actor takes
A delivery draft is the draft of `implement.pr` that the ready path takes, with no owner label. Its failed check has a repair owner only in mode `on`, for a class in FIX_CHECK_CLASSES, while the unit of the head and the check has not ended with no repair. For each other failed or cancelled check, the latest run of each name, and for a conflict, the `stop` due step SHALL stop the item once: one stop comment, Status Blocked, `implement.stopped`, the class and `implement.result` stopped.

#### Scenario: A failed check that no unit repairs
- **WHEN** the `Semantic PR title` check of a drafted delivery draft fails, and the row runs three rounds
- **THEN** the item is Blocked with the class `ci_infra`, and it holds one stop comment that names `Semantic PR title`

#### Scenario: A cancelled check
- **WHEN** the `Tests & Coverage` check of a drafted delivery draft is cancelled
- **THEN** the item is Blocked with the class `ci_infra`, and it holds one stop comment that names the check

#### Scenario: A conflict
- **WHEN** a drafted delivery draft has passing checks and a conflict with its base
- **THEN** the item is Blocked with the class `conflict`, and it holds one stop comment that names the conflict

#### Scenario: A unit that ended with no repair
- **WHEN** the fix-checks unit of the head and the failed `Tests & Coverage` check of a drafted delivery draft ended with the result `failed`, in mode `on`
- **THEN** the item is Blocked with the class `test` and `implement.result` stopped

#### Scenario: A mode other than on
- **WHEN** the `Tests & Coverage` check of a drafted delivery draft fails in mode `plan` or `off`
- **THEN** the item is Blocked with the class `test`

#### Scenario: A unit owns the check
- **WHEN** the `Tests & Coverage` check of a drafted delivery draft fails in mode `on`, and no unit of the head and the check ended
- **THEN** the row starts a fix Job with `--confirm`, and the item stays In Review

#### Scenario: A Staged item delivers on its plan pull request
- **WHEN** the drafted delivery draft is also the plan pull request of its item, and it has a cancelled check or a conflict
- **THEN** the item is Blocked, as for another delivery draft

#### Scenario: A claimed item
- **WHEN** the item or the pull request of a drafted delivery draft with a cancelled check holds an owner label
- **THEN** the row stops nothing

#### Scenario: A stop, then green checks
- **WHEN** the row stopped the item for a cancelled check, and the check passes on the same head
- **THEN** the row runs no ready path, and the item stays Blocked

#### Scenario: A cancelled run beside a newer passing run
- **WHEN** the rollup holds a cancelled run of a check and a newer passing run of the same check
- **THEN** the row stops nothing and runs the ready path

### Requirement: A scoped watch round reads only the delivered pull requests
`watch_round` SHALL take the pull request numbers of a delivery. With numbers it SHALL read a number over REST only when the store records it as the `stage.pr` of an open item or the watch ledger holds it, SHALL skip the GraphQL listing of the open pull requests, and SHALL send no request for a number that neither source names. With no numbers it SHALL read the open pull requests as the poll round does.

#### Scenario: A scoped round reads the delivered pull request
- **WHEN** the store holds open staged drafts 42 and 43, and `watch_round` is called with the pull numbers (42,)
- **THEN** the round reads pull request 42 and sends no request for pull request 43

#### Scenario: A scoped round for an unknown pull request sends no request
- **WHEN** `watch_round` is called with the pull numbers (99,), and neither the store nor the watch ledger names pull request 99
- **THEN** the round sends no request and returns the empty round result

#### Scenario: A round with no numbers reads the listing
- **WHEN** `watch_round` is called with no pull numbers
- **THEN** it reads the open pull requests with one GraphQL query, as the poll does

### Requirement: REST fallback tests backoff before reading check runs
In the REST fallback path (`_process_rest_pulls`), `watch` SHALL test whether the pull request head and base match an active failed-head backoff entry in the watch ledger before calling `read_check_runs`, skipping check-run requests and recording the pull request in `failed_heads` while counting it in `watched`.

#### Scenario: Failed head in backoff under GraphQL hold triggers zero check-run reads
- **WHEN** GraphQL quota is on hold, `watch_round` falls back to REST for an open pull request whose ledger entry holds verdict `FAILED`, the same head SHA and base branch, and `next_read_at` in the future
- **THEN** zero REST requests are sent to `/check-runs`, the result includes the pull request number in `failed_heads`, and `watched` counts it

### Requirement: The watch row takes a plan pull request by its number and its head branch
The watch row SHALL take a pull request as the plan of an item only when the record of the item names the number of the pull request as `stage.pr` and its head branch as `stage.branch`, and `stage.branch` names the item. For a pull request whose head branch is not the recorded branch, the row SHALL send no write for the item of the record.

#### Scenario: A draft on the recorded branch
- **WHEN** the record of an open item names a green draft of the bot and the branch `feat/1-plan-the-rows`, and the head branch of the draft is that branch
- **THEN** the row marks the draft ready and records `stage.ready`

#### Scenario: A draft whose head branch is not the recorded branch
- **WHEN** the record of an open item names a green draft and the branch `feat/1-plan-the-rows`, and the head branch of the draft is `feat/4107-add-the-rows`
- **THEN** the draft is not the plan of the item, and the round sends no write, over GraphQL and over REST

#### Scenario: Two items record one number
- **WHEN** two open items record the number of one draft, and the head branch of the draft is the recorded branch of the second item
- **THEN** only the second item gets `stage.ready`

### Requirement: Each round of the watch row reads the head branch before it takes a plan
The GraphQL query of the watch row SHALL read the head branch of each open pull request (`headRefName`). The REST round and the scoped round SHALL read the pull request before they take the item of a record. The read of the plans that are no more open SHALL compare the head branch before it records `stage.ready` or sets a Status.

#### Scenario: The REST round reads a draft on the recorded branch
- **WHEN** the GraphQL quota is on hold, and the record of an open item names a green draft of the bot and its head branch
- **THEN** the row marks the draft ready

#### Scenario: A merged pull request on another branch
- **WHEN** the record of an open item names a pull request that merged and whose head branch is not the recorded branch
- **THEN** the round records no `stage.ready` for the item and sets no Status, in a reconciling round and in a scoped round

#### Scenario: A merged pull request on the recorded branch
- **WHEN** the record of an open item names a pull request that merged and whose head branch is the recorded branch
- **THEN** the round records `stage.ready` for the item
