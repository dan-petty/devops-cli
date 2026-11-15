## ADDED Requirements

### Requirement: Empty check runs report pending
When a poll of a pull request reads zero check runs on a checked head, the monitor SHALL report the check status as pending rather than ready.

#### Scenario: Zero check runs on poll
- **WHEN** a pull request is polled and reports zero check runs
- **THEN** the verdict is PENDING

### Requirement: Unified pull request verdict
The watch step SHALL provide a single pure verdict function that returns PENDING, READY, FAILED, CONFLICT, BEHIND, THREADS, MERGED, CLOSED, or HEAD_MOVED.

#### Scenario: Skip CI commit message
- **WHEN** a pull request head commit message contains `[skip ci]`
- **THEN** the verdict function returns no verdict

#### Scenario: State outcomes table
- **WHEN** a pull request is in a given state
- **THEN** the verdict function returns the expected verdict enum

### Requirement: One mark-ready wrapper
The ready step SHALL be the single wrapper executing `gh pr ready`, and it SHALL verify that the remote head commit matches the expected head before transitioning.

#### Scenario: Head matches expected head
- **WHEN** the remote pull request head SHA equals the expected head SHA
- **THEN** `mark_ready` transitions the draft to ready
