## ADDED Requirements

### Requirement: The selection reads the checks of the plan pull request
The implement selection SHALL read the check runs at the head of the plan pull request of a Staged item and SHALL leave the item out when a check failed, was cancelled, is pending, or cannot be read. It SHALL select the item when every check settled as a pass or a skip.

#### Scenario: A plan check fails
- **WHEN** a check of the plan pull request has the `fail` bucket
- **THEN** the selection selects no target and the reason names the failed check

#### Scenario: A plan check is cancelled
- **WHEN** a check of the plan pull request has the `cancel` bucket
- **THEN** the selection selects no target and the reason names the cancelled check

#### Scenario: A plan check still runs
- **WHEN** a check of the plan pull request has the `pending` bucket
- **THEN** the selection selects no target and the reason names the running check

#### Scenario: The checks cannot be read
- **WHEN** the read returns an unread verdict
- **THEN** the selection selects no target and the reason holds the unread reason

#### Scenario: Every plan check passes
- **WHEN** every check of the plan pull request has the `pass` or `skipping` bucket
- **THEN** the selection selects the item with its branch and pull request number

#### Scenario: The head of the plan pull request names the checks
- **WHEN** the selection judges one Staged item whose record holds `stage.pr`
- **THEN** the reader receives the head SHA of that pull request once
