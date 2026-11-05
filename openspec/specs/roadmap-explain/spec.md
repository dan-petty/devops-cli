# roadmap-explain Specification

## Purpose
How `devops roadmap explain` tells a person or an agent, for one roadmap issue, whether the stage job and the implement job take it, and the first rule that stops each job when they do not.

## Requirements

### Requirement: The command names the first rule that stops each job
`devops roadmap explain <issue>` SHALL print, for the refine job, the stage job and the implement job, `yes` or `no`. For `no` it SHALL print the reason of the first rule that fails. The rules and their order SHALL be those of the job. The reasons SHALL be the texts of the "Left out" list of `stage --plan` and `implement --plan`, and, for refine, the wait of the item. The rules are not an item or closed, the filter, the rules of the job, then the limit of a run.

#### Scenario: An item of medium effort
- **WHEN** a Planned item holds `effort/medium` and the implement filter asks for `effort/low`
- **THEN** the implement job is `no` and the reason names the family `effort`, the value `low` that the filter takes, and the value `medium` that the item has

#### Scenario: A claimed item
- **WHEN** a Ready item that the filter names holds `owner/human`
- **THEN** the stage job and the implement job are `no`, and the reason is "It is claimed by human."

#### Scenario: A stopped item
- **WHEN** a Staged item holds `implement.stopped` and no retry comment follows
- **THEN** the implement job is `no` and the reason is the text of the stop

#### Scenario: An unplanned item
- **WHEN** a Ready item of low effort has no staged branch and no change folder on the default branch
- **THEN** the implement job is `no` and the reason says that it is neither Staged nor Planned, and the stage job is `yes`

#### Scenario: A recorded group over the budget
- **WHEN** the record of a Ready item holds `stage.needs_split` made with the file cap of now
- **THEN** the stage job is `no` and the reason is the text of the recorded split

#### Scenario: Not an item or closed
- **WHEN** the issue is closed, has no priority label, or does not exist
- **THEN** the three jobs are `no` and the reason says that it is closed or that it is no item

#### Scenario: The limit of a run
- **WHEN** an item passes every rule and the limit of a run is filled by items of higher priority
- **THEN** the job is `no` and the reason names the limit

#### Scenario: An item the job takes
- **WHEN** an item passes every rule within the limit
- **THEN** the job is `yes`

#### Scenario: An item that waits on a person in refine
- **WHEN** a New item's last refine round left a question for a person and no reply, closed issue or changed file follows
- **THEN** the refine job is `no` and the reason says that the item waits on a person and what makes refine look again

#### Scenario: An item the stage job returned twice
- **WHEN** a New item has `refine.returned_body_hash` equal to its `refine.body_hash` and a stage comment follows refine's last comment
- **THEN** the refine job is `no` and the reason says that the stage job returned the item twice on the same body

#### Scenario: A New item with no round
- **WHEN** a New item has no refine record
- **THEN** the refine job is `yes`

### Requirement: The command makes no model call and no write
`explain` SHALL call no model, SHALL write nothing to GitHub or to git, and SHALL change no label, comment or record. It SHALL read the issues, the branches and the change folders that the plan of the job reads. With `--trace` it SHALL read the one issue.

#### Scenario: A read-only run
- **WHEN** `explain` runs with a model client that fails the test when it is built and a store that records writes
- **THEN** the exit status is 0 and the store records no write

#### Scenario: A read-only run of the trace
- **WHEN** `explain 7 --trace` runs with a model client that fails the test when it is built and a store that records writes
- **THEN** the exit status is 0, the store records no write, and it reads issue 7 once

### Requirement: The dry run lists the reads
`explain --dry-run` SHALL make no request and SHALL list the reads of a run. Its dry-run class SHALL be `request-plan`.

#### Scenario: A dry run
- **WHEN** `explain 7 --dry-run` runs with processes and sockets refused
- **THEN** the exit status is 0, the output says that no request was made and lists the read of issue 7, and it lists no write

### Requirement: The options replace the filter and the limit for one run
`--filter family=value` SHALL replace the filter of both jobs and `--limit` SHALL replace the limit of both jobs. With neither, `explain` SHALL use the filter and the limit that the Service uses for each job.

#### Scenario: A filter option
- **WHEN** `explain 7 --filter effort=medium` runs for an item with `effort/medium`
- **THEN** the filter reason does not appear for either job

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

### Requirement: The command names the limit on Planned items
For the stage job, `devops roadmap explain <issue>` SHALL print `no` for an item that the limit `roadmap.stage.planned_limit` holds, and the reason SHALL name the setting and the count of open Planned items. When no `--limit` or other option names it, the limit SHALL be the setting that the Service uses.

#### Scenario: An item that the limit holds
- **WHEN** 2 items are Planned, the setting is 2, and a Ready item passes every other rule
- **THEN** the stage job is `no`, and the reason names `roadmap.stage.planned_limit` and the count 2

#### Scenario: An item under the limit
- **WHEN** 2 items are Planned, the setting is 3, and a Ready item passes every other rule
- **THEN** the stage job is `yes`

#### Scenario: The limit from the settings
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_STAGE_PLANNED_LIMIT` holds 1, 1 item is Planned, and a Ready item passes every other rule
- **THEN** the stage job is `no` with the reason of the limit

### Requirement: The command reports an item that the stage job holds for a retry
For the stage job, `devops roadmap explain <issue>` SHALL read `stage.failed_at` and `stage.failed_error` in the job record of the item on GitHub. When the failure is younger than `roadmap.stage.retry_hours` hours, the stage job SHALL be `no`, and the reason SHALL name the error class and the time after which the job takes the item again.

#### Scenario: A held item
- **WHEN** the job record of a Ready item holds a failure of 5 minutes ago with the class `AIClientError`
- **THEN** the stage job is `no` and the reason names `AIClientError` and the time of the retry

### Requirement: The trace option prints an attempt
`explain <issue> --trace` SHALL print an `attempt` event as one line with its step, its number, its outcome, its failure class, its evidence and what follows.

#### Scenario: An attempt
- **WHEN** the trace holds the attempt 1 of `group 1` that failed with class `lint` and is followed by `repair`
- **THEN** the output line names `group 1`, attempt 1, the outcome `failed`, the class `lint` and `repair`

### Requirement: The implement verdict names the effort set and the fallback pass
`devops roadmap explain` SHALL name, on a line under the implement job, the effort set of the job and whether the fallback pass applies to the item. The fallback pass SHALL apply to an item only when the item's effort is the effort of the pass in use and that pass is not the first value of the set. When the filter names `effort`, the line SHALL say that the set does not apply.

#### Scenario: A medium-effort item uses the fallback
- **WHEN** the user runs `devops roadmap explain <number>` on a Ready medium-effort item while no low-effort item is selectable
- **THEN** the output names the effort set `low,medium` and says that the fallback pass applies to the item

#### Scenario: A medium-effort item waits for a low-effort item
- **WHEN** the user runs `devops roadmap explain <number>` on a Ready medium-effort item while a Ready low-effort item is selectable
- **THEN** the implement job is `no`, the reason names the effort `low` that the run takes first, and the output says that the fallback pass does not apply to the item

#### Scenario: A high-effort item is outside the set
- **WHEN** the user runs `devops roadmap explain <number>` on a Ready high-effort item
- **THEN** the implement job is `no` and the reason names the family `effort`, the values `low or medium`, and the value `high`
