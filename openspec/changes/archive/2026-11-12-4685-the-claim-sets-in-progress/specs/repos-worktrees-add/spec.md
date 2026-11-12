## ADDED Requirements

### Requirement: The claim of an agent sets the Status In Progress
After a claim that is made, `add` SHALL set `status/in-progress` on the item when its Status is New, Ready or Planned, or when it has none, and SHALL keep every other Status, Blocked included. A failed Status write SHALL NOT stop the command: the exit status is 0, `claimed` stays true, and the report holds the reason in `status_error`. A dry run SHALL make no request and SHALL list the Status write.

#### Scenario: A Ready item
- **WHEN** item 2337 holds `status/ready` and the user runs `add 2337 --type feat --slug worktrees-add`
- **THEN** the item holds `owner/agent` and `status/in-progress`

#### Scenario: A Blocked item
- **WHEN** item 2337 holds `status/blocked`, also with `implement.stopped` on record, and the user runs `add`
- **THEN** the item still holds `status/blocked`

#### Scenario: An item In Review
- **WHEN** item 2337 holds `status/in-review` and the user runs `add`
- **THEN** the item still holds `status/in-review`

#### Scenario: The Status write fails
- **WHEN** the write of the Status fails with "HTTP 502"
- **THEN** the exit status is 0, the item holds `owner/agent`, `claimed` is true, and `status_error` holds the reason
- **AND** the table output prints the reason as a warning

#### Scenario: A dry run
- **WHEN** the user runs `add 2337 --type feat --slug worktrees-add --dry-run`
- **THEN** the store records no write and the plan lists the write of the Status with its condition
