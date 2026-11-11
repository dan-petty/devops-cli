## MODIFIED Requirements

### Requirement: The trace option prints the trace of the last run
`explain <issue> --trace` SHALL print the events of `implement.trace` in the record of the issue, oldest first, one line each, then the count of events that the bound dropped, and SHALL print no verdict. A `tool` event that holds an exit status SHALL show it in its line. With no trace it SHALL say so and exit 0. A trace that is not readable SHALL stop the command with exit status 1 and an error that names `implement.trace`.

#### Scenario: A trace
- **WHEN** the record of issue 7 holds a trace of a model call, a tool call and a check, and `explain 7 --trace` runs
- **THEN** the output has three lines in that order, each with its step, and no `yes` or `no` of a job

#### Scenario: A shell call with an exit status
- **WHEN** the trace holds a `tool` event of a shell call with the exit status 128
- **THEN** its line says `exit status 128`

#### Scenario: Dropped events
- **WHEN** the trace holds `dropped` 12
- **THEN** the output says that 12 earlier events are not kept

#### Scenario: No trace
- **WHEN** the record of issue 7 has no `implement.trace`
- **THEN** the output says that the issue has no trace, and the exit status is 0

#### Scenario: A trace that is not readable
- **WHEN** the value of `implement.trace` is not JSON
- **THEN** the exit status is 1 and the error names `implement.trace`

#### Scenario: A dry run with the option
- **WHEN** `explain 7 --trace --dry-run` runs with processes and sockets refused
- **THEN** the output lists the read of issue 7 and no read of a branch or a change folder
