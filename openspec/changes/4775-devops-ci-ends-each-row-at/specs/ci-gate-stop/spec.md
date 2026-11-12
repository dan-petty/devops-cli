## Purpose
How the gate run of `devops ci` stops its rows when a stop signal or a time limit ends it, and how the limits of the pre-push hooks fit in the limit of the shell around them.

## ADDED Requirements

### Requirement: A stop signal stops each running row of the gate
When Ctrl-C, SIGTERM or SIGHUP reaches a run of `devops ci` that runs its rows, the run SHALL stop the process group of each row that still runs. It SHALL print a line for each such row with the title of the row and the time it ran, and SHALL exit as cancelled, with exit status 130. A signal that the process ignores SHALL stay ignored.

#### Scenario: coreutils timeout ends the gate
- **WHEN** `timeout` sends SIGTERM to `devops ci --check --only format` while the row runs a child and a grandchild
- **THEN** the child and the grandchild stop
- **AND** the output has the line of `ruff format` with `stopped after`
- **AND** `devops ci` exits with status 130

### Requirement: The pre-push hooks end before the agent shell limit
Each hook of the pre-push stage SHALL run under a coreutils `timeout` limit. The sum of these limits plus 25 s for the start of pre-commit, the transfer and the stop of the rows SHALL be less than 120 s, the default limit of the shell tool of an agent.

#### Scenario: A hook with no limit
- **WHEN** a pre-push hook has no `timeout` limit
- **THEN** the structural test fails and names the hook

#### Scenario: The limits add up to 121 s
- **WHEN** the limits of the pre-push hooks plus 25 s are 121 s
- **THEN** the structural test fails and gives the total
