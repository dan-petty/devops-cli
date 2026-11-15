# pr-monitor Specification

## Purpose
The pull-request monitor polls one pull request until its checks and reviews settle or the watch times out, and it rides out a slow GitHub read.

## Requirements

### Requirement: A failed read does not end the watch
`monitor_pr` SHALL count a failed read of the pull request as a poll with no new data, print a warning, and poll again at its interval. It SHALL stop with the last error only after three failed reads in a row, or when its timeout passes.

#### Scenario: One failed read
- **WHEN** a poll raises `GitHubOperationError` and the next poll returns a terminal status
- **THEN** the monitor returns that result and prints a warning that names the failure

#### Scenario: Three failed reads in a row
- **WHEN** three polls in a row raise `GitHubOperationError`
- **THEN** the monitor raises the last error

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
