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

## REMOVED Requirements

### Requirement: The watch row marks a delivery draft ready only after a fix
**Reason**: The implement Job ends at the draft, so the row also takes a draft whose implement Job ended at the draft (#6559).
**Migration**: The requirement "The watch row marks a delivery draft ready after a fix or a drafted end" holds the rule.
