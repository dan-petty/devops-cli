## MODIFIED Requirements

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
