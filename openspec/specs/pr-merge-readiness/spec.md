# pr-merge-readiness Specification

## Purpose
How `devops pr ready` and `devops pr monitor` judge a pull request from the one merge-readiness verdict that `devops pr check-readiness` prints, and map it to their exit codes.

## Requirements

### Requirement: The monitor waits until the checks settle and names every blocker
`devops pr monitor` SHALL keep waiting while a check of the head commit runs, whatever other blockers it sees. When no check runs, it SHALL return once, naming every blocker, and SHALL exit 1 when a check failed or could not be read, 2 for any other blocker, 0 with no blocker, and 3 when its timeout passes first.

#### Scenario: A check fails after an open thread is first seen
- **WHEN** the head commit has two running checks and one unresolved review thread, and on the next poll one check passed and the other failed
- **THEN** the monitor reads the pull request twice, exits 1, and names the failed check and the thread

#### Scenario: The checks still run at the timeout
- **WHEN** a check of the head commit still runs when the timeout passes
- **THEN** the monitor exits 3 and names the running check

### Requirement: The monitor and pr ready map the verdict to their exit codes
`devops pr monitor` and `devops pr ready` SHALL judge a pull request through the merge-readiness verdict. `devops pr ready` SHALL exit 1 when a check failed or could not be read and 8 while a check runs, and SHALL print each other blocker as a warning and mark the pull request ready.

#### Scenario: The exit codes
- **WHEN** the pull request is ready, has a running check, a failed check, unread checks, an unresolved review thread, or is a draft
- **THEN** `pr ready` exits 0, 8, 1, 1, 0 and 0, and `pr monitor` exits 0, 3, 1, 1, 2 and 2

#### Scenario: A missing priority label does not stop pr ready
- **WHEN** a draft pull request with passing checks closes an issue that holds no `priority/*` label
- **THEN** `pr ready` prints the blocker as a warning, marks the pull request ready, and exits 0

### Requirement: A pull request that cannot be read stops pr ready
`devops pr ready` SHALL stop with exit 1 and name the error when it cannot read the pull request, unless `--force` is given.

#### Scenario: The read fails
- **WHEN** GitHub answers the read of the pull request with an error
- **THEN** `pr ready` exits 1, names the error, and does not mark the pull request ready

### Requirement: A branch behind its base is no blocker
No readiness command SHALL block a pull request because its branch is behind its base.

#### Scenario: The branch is behind
- **WHEN** GitHub reports `mergeable: true` and `mergeable_state: behind`, and nothing else blocks
- **THEN** the verdict has no blocker

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
