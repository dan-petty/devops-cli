# roadmap-store-write-failure Specification

## Purpose
What the error of a failed roadmap store write holds: the classified failure where the gh
classifier names one, else the gh command up to its first field value, the exit code, the full
issue title and the stderr of gh.

## Requirements

### Requirement: Full title in the create error
When gh's stderr matches no classified failure, the error for a failed `gh issue create` SHALL name the full issue title that intake sent.

#### Scenario: A title longer than the store's 64-character cut fails to open
- **WHEN** A unit test calls `GitHubRoadmapStore.create_issue` with a title longer than 64 characters and a fake `gh` result of exit 1 and stderr `unexpected end of JSON input`
- **THEN** The test asserts the error text contains the complete title and not the title cut to 64 characters

### Requirement: Command, exit code and stderr in the create error
When gh's stderr matches no classified failure, the error for a failed `gh issue create` SHALL name the `gh api -X POST repos/<repo>/issues` command, its exit code and its stderr.

#### Scenario: gh refuses the create with a validation error
- **WHEN** A unit test gives `GitHubRoadmapStore.create_issue` a fake `gh` result of exit 1 and stderr `HTTP 422: Validation Failed`
- **THEN** The test asserts the error text contains `gh api -X POST repos/dan-petty/devops-cli/issues`, `exit 1` and `stderr: HTTP 422: Validation Failed`

### Requirement: gh stderr is reported as stderr
The error for a failed `gh issue create` SHALL label the text gh wrote to stderr as stderr, so it is not mistaken for a JSON parse failure of intake.

#### Scenario: gh exits nonzero with empty stdout
- **WHEN** A unit test gives `GitHubRoadmapStore.create_issue` a fake `gh` result of exit 1, empty stdout and stderr `unexpected end of JSON input`
- **THEN** The test asserts the error text contains `stderr: unexpect` and not `GitHub returned malformed issue after it was opened`

### Requirement: Empty stderr is explicit
The error for a failed `gh issue create` SHALL state when the stderr of `gh` is empty.

#### Scenario: gh fails with no stderr
- **WHEN** A unit test gives `GitHubRoadmapStore.create_issue` a fake `gh` result of exit 1 and empty stdout and stderr
- **THEN** The test asserts the error text contains `stderr: (empty)`
