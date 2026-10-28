## Purpose

How `devops pr ready` and `devops pr monitor` judge a pull request from the one merge-readiness verdict that `devops pr check-readiness` prints, and map it to their exit codes.

## ADDED Requirements

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
