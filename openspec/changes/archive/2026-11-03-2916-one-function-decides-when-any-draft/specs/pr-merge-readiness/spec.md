## ADDED Requirements

### Requirement: pr ready asks the readiness function
`devops pr ready` SHALL ask `draft_readiness` for the pull request, with the word of the author given. It SHALL exit 1 for a refusal and name each unticked task group of an implement pull request, and SHALL exit 8 for a wait. `--force` SHALL skip the question. A read of the item that fails SHALL stop the command with exit 1 and the error.

#### Scenario: A partial implement pull request
- **WHEN** a person runs `devops pr ready` for a draft whose item holds `implement.pr` of it and whose `tasks.md` has an unticked group 2
- **THEN** the command exits 1, prints group 2, and marks nothing

#### Scenario: The exit codes of the checks stay
- **WHEN** the draft has a running check, a failed check, or unread checks
- **THEN** the command exits 8, 1 and 1

#### Scenario: A branch with no item
- **WHEN** the head branch names no issue and the checks pass
- **THEN** the command marks the pull request ready as before

#### Scenario: The record cannot be read
- **WHEN** GitHub refuses the read of the item that the head branch names
- **THEN** the command exits 1 with the error, and `--force` marks the pull request ready

### Requirement: check-readiness names the unticked group
`devops pr check-readiness` SHALL add one blocker and exit non-zero when `draft_readiness` refuses an implement pull request, and the blocker SHALL name each unticked task group. It SHALL add none for a pull request with no recorded item. A read of the item that fails SHALL be a blocker that names the error.

#### Scenario: A partial implement pull request blocks
- **WHEN** a user runs `devops pr check-readiness` for an implement pull request with an unticked group
- **THEN** the command exits non-zero and prints the name of the group

#### Scenario: A complete implement pull request
- **WHEN** every group of the archived `tasks.md` is ticked and the other rules pass
- **THEN** the command adds no readiness blocker

#### Scenario: A pull request with no recorded item
- **WHEN** the head branch names no issue
- **THEN** the command adds no readiness blocker and reads no item
