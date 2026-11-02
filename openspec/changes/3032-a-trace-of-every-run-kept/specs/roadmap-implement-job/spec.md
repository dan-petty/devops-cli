## ADDED Requirements

### Requirement: The job keeps the trace of its run
The job SHALL clear `implement.trace` when a run starts, and SHALL write it with each record of a passed group, with a stop and with the ready mark. The value SHALL be JSON with the events and the count `dropped`. When the value is longer than `CONST_ROADMAP_IMPLEMENT_TRACE_CHARS` characters, the job SHALL drop the oldest events and count them in `dropped`.

#### Scenario: A trace that is too long
- **WHEN** a run makes more events than fit in `CONST_ROADMAP_IMPLEMENT_TRACE_CHARS` characters
- **THEN** the value is not longer than the bound, it holds the newest events whole, and `dropped` counts the others

#### Scenario: A new run
- **WHEN** a person retries a stopped item
- **THEN** the job clears `implement.trace` before its first step, and the record holds only the events of the new run

#### Scenario: A Job that ends after a group
- **WHEN** the Service ends a Job after the record of group 1 and before the stop
- **THEN** the record holds the events of group 1

### Requirement: The stop comment shows a table of the steps
The stop comment SHALL hold the table of the comment on the pull request, after the lines of the failure class and before the reason. The row of the step that stopped SHALL be in it. The last failing command SHALL be the command of the last `check` event with an exit status other than 0, or the name of the check of the pull request that failed.

#### Scenario: A step that stops on a failed command
- **WHEN** group 2 stops after one repair round, with 4,100 input and 320 output tokens, and `mypy` exited 1
- **THEN** the table holds the row `group 2`, 2 attempts, `4100/320` and the `mypy` command

#### Scenario: A failed check of the pull request
- **WHEN** the checks of the pull request stop the item with the check `Tests & Coverage` failed
- **THEN** the table holds a row for the step of the checks with `Tests & Coverage` as its last failing command

### Requirement: The table cuts its rows and its cells
The table SHALL list at most `CONST_ROADMAP_IMPLEMENT_TABLE_ROWS` rows, the newest, SHALL cut a command to `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS` characters, and SHALL escape a `|` in a cell.

#### Scenario: A command with a pipe
- **WHEN** the last failing command holds `a | b`
- **THEN** the row holds `a \| b` in one cell

#### Scenario: More rows than the bound
- **WHEN** a run has more steps than `CONST_ROADMAP_IMPLEMENT_TABLE_ROWS`
- **THEN** the table holds the newest rows only

## MODIFIED Requirements

### Requirement: The job record
The job SHALL keep `implement.group` (the last group that passed), `implement.sha` (the commit it ended on), `implement.branch` (the branch of the pull request), `implement.pr` (the pull request), `implement.stopped`, `implement.spend` and `implement.trace` in the job record of the item. The spend SHALL be the requests, input tokens and output tokens of every step the job ran.

#### Scenario: Spend
- **WHEN** two steps used 3 and 4 requests
- **THEN** the record of the spend holds 7 requests

#### Scenario: The branch
- **WHEN** the job takes a Staged item and a Planned item to a ready pull request
- **THEN** the record of each holds its branch and its pull request

#### Scenario: The trace
- **WHEN** the job takes an item to a ready pull request
- **THEN** the record holds `implement.trace` with the events of the steps, the scoped checks and the commands of the job

### Requirement: The comment on the pull request shows the repair rounds and the scoped checks
The comment of the job on the pull request SHALL show a table with one row for each step: the step, its status, its attempts (the first turn and the repair rounds), its tokens in and out and its last failing command. It SHALL show one line for each run of a scoped check with its name, its result and its seconds.

#### Scenario: One repair round
- **WHEN** the step of group 1 used one repair round and the scoped checks passed
- **THEN** the row of group 1 shows 2 attempts, and a line for each scoped check shows `passed` and its seconds
