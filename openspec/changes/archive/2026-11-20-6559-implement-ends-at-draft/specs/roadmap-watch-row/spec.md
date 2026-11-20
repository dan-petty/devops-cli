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

### Requirement: The watch row stops the item of a delivery draft that no actor takes
For a bot delivery draft that the ready path takes and whose item holds no stop, the `stop` due step SHALL stop the item once: one stop comment that names the check or the conflict, Status Blocked, `implement.stopped` equal to `pull request`, and the class `ci_infra` for a check or `conflict` for a conflict. The row SHALL add no re-run and no retry.

#### Scenario: A failed check that no unit repairs
- **WHEN** the `Semantic PR title` check of a drafted delivery draft fails, and the row runs three rounds
- **THEN** the item is Blocked with the class `ci_infra`, and it holds one stop comment that names `Semantic PR title`

#### Scenario: A cancelled check
- **WHEN** the `Tests & Coverage` check of a drafted delivery draft is cancelled
- **THEN** the item is Blocked with the class `ci_infra`, and it holds one stop comment that names the check

#### Scenario: A conflict
- **WHEN** a drafted delivery draft has passing checks and a conflict with its base
- **THEN** the item is Blocked with the class `conflict`, and it holds one stop comment that names the conflict

## REMOVED Requirements

### Requirement: The watch row marks a delivery draft ready only after a fix
**Reason**: The implement Job ends at the draft, so the row also takes a draft whose implement Job ended at the draft (#6559).
**Migration**: The requirement "The watch row marks a delivery draft ready after a fix or a drafted end" holds the rule.

## MODIFIED Requirements

### Requirement: The due_steps pure function routes pull request states
`due_steps(state)` SHALL return the due lifecycle actions of a pull request, and none for an item with a live unit. A FAILED bot pull request whose failed check has the class test, lint, types or plan check SHALL get `fix_checks`. A bot delivery whose check no unit repairs (`unrepaired_check`) or whose verdict is CONFLICT SHALL get `stop`; a bot plan SHALL get neither.

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
- **THEN** `due_steps` returns `stop` and no `fix_checks`

#### Scenario: A cancelled check of a bot delivery
- **WHEN** the `Tests & Coverage` check of a bot delivery is cancelled
- **THEN** `due_steps` returns `stop`

### Requirement: The watch row marks a delivery draft ready after a fix or a drafted end
For a delivery draft with the verdict READY whose item records `fix_checks.result` as `repaired` or `implement.result` as `drafted`, the watch row SHALL run the ready path of the step `fix-checks` only, once for each head that got a report from it, with `--confirm` only in mode `on` of `roadmap.fix_checks.mode`. The row SHALL send no request for each other delivery draft.

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
