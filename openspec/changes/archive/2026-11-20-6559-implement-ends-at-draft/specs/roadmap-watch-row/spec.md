## ADDED Requirements

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

## REMOVED Requirements

### Requirement: The watch row marks a delivery draft ready only after a fix
**Reason**: The implement Job ends at the draft, so the row also takes a draft whose implement Job ended at the draft (#6559).
**Migration**: The requirement "The watch row marks a delivery draft ready after a fix or a drafted end" holds the rule.

## MODIFIED Requirements

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

### Requirement: The watch row marks a delivery draft ready after a fix or a drafted end
For a delivery draft with the verdict READY whose item holds no stop and records `fix_checks.result` as `repaired` or `implement.result` as `drafted`, the watch row SHALL run the ready path of the step `fix-checks` only, once for each head that got a report from it, with `--confirm` only in mode `on` of `roadmap.fix_checks.mode`. A Staged item that delivers on its plan pull request SHALL get the same guards on the plan path. The row SHALL send no request for each other delivery draft.

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
