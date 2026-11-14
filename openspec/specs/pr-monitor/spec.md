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
