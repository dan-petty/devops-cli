## ADDED Requirements

### Requirement: The trace option prints the trace of the last run
`explain <issue> --trace` SHALL print the events of `implement.trace` in the record of the issue, oldest first, one line each, then the count of events that the bound dropped, and SHALL print no verdict. With no trace it SHALL say so and exit 0. A trace that is not readable SHALL stop the command with exit status 1 and an error that names `implement.trace`.

#### Scenario: A trace
- **WHEN** the record of issue 7 holds a trace of a model call, a tool call and a check, and `explain 7 --trace` runs
- **THEN** the output has three lines in that order, each with its step, and no `yes` or `no` of a job

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

## MODIFIED Requirements

### Requirement: The command makes no model call and no write
`explain` SHALL call no model, SHALL write nothing to GitHub or to git, and SHALL change no label, comment or record. It SHALL read the issues, the branches and the change folders that the plan of the job reads. With `--trace` it SHALL read the one issue.

#### Scenario: A read-only run
- **WHEN** `explain` runs with a model client that fails the test when it is built and a store that records writes
- **THEN** the exit status is 0 and the store records no write

#### Scenario: A read-only run of the trace
- **WHEN** `explain 7 --trace` runs with a model client that fails the test when it is built and a store that records writes
- **THEN** the exit status is 0, the store records no write, and it reads issue 7 once
