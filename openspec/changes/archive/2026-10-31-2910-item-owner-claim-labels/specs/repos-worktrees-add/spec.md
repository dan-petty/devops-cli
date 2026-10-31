# Spec Delta

## ADDED Requirements

### Requirement: A new worktree claims the issue for an agent
After it makes the worktree, `add` SHALL claim the issue as `owner/agent` on the roadmap of the repository of `origin`. A claim that cannot be made SHALL NOT stop the command: the worktree stays, the exit status is 0, and the report holds the reason in `claim_error`. A dry run SHALL make no request and SHALL list the requests of the claim.

#### Scenario: A free item
- **WHEN** the user runs `add 2337 --type feat --slug worktrees-add` and item 2337 has no owner
- **THEN** the worktree exists and item 2337 holds `owner/agent`

#### Scenario: A person holds the item
- **WHEN** item 2337 holds `owner/human` and the user runs `add`
- **THEN** the worktree exists, the exit status is 0, the item still holds `owner/human`, and the report names `claim_error`

#### Scenario: The label write fails
- **WHEN** the write of the label fails with "HTTP 502"
- **THEN** the worktree exists, the exit status is 0, and `claim_error` holds the reason

#### Scenario: A table report
- **WHEN** the claim fails and the format is the table
- **THEN** the output prints the reason as a warning

#### Scenario: A refused issue
- **WHEN** a worktree already holds the issue and the user runs `add`
- **THEN** the command exits 1 and the item is unchanged

#### Scenario: A dry run
- **WHEN** the user runs `add 2337 --type feat --slug worktrees-add --dry-run`
- **THEN** the store records no write and the plan lists the read and the write of the owner label
