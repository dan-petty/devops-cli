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
The command SHALL call no model, SHALL write nothing to GitHub or to git, and SHALL change no label, comment or record. It SHALL read the issues, the branches and the change folders that the plan of the job reads. With `--trace` it SHALL read the one issue. It SHALL report the totals from the job record of the issue that it reads.

#### Scenario: A read-only run
- **WHEN** `explain` runs with a model client that fails the test when it is built and a store that records writes
- **THEN** the exit status is 0 and the store records no write

#### Scenario: A read-only run of the trace
- **WHEN** `explain 7 --trace` runs with a model client that fails the test when it is built and a store that records writes
- **THEN** the exit status is 0, the store records no write, and it reads issue 7 once

#### Scenario: A run that reports totals
- **WHEN** `explain 7` runs on an item whose record holds a trace, with a model client that fails the test when it is built and a store that records writes
- **THEN** the output holds the totals and the store records no write

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

### Requirement: The command names the limit on Planned items
For the stage job, `devops roadmap explain <issue>` SHALL print `no` for an item that the limit `roadmap.stage.planned_limit` holds, and the reason SHALL name the setting, the count of open Planned items and the priorities that pass the limit. It SHALL print `yes` for an item with the priority `P1-High` that passes every other rule. When no `--limit` or other option names it, the limit SHALL be the setting that the Service uses.

#### Scenario: An item that the limit holds
- **WHEN** 2 items are Planned, the setting is 2, and a Ready `P2-Medium` item passes every other rule
- **THEN** the stage job is `no`, and the reason names `roadmap.stage.planned_limit`, the count 2, and `P0-Critical or P1-High`

#### Scenario: A P1 item at the limit
- **WHEN** 1 item is Planned, the setting is 1, and a Ready `P1-High` item passes every other rule
- **THEN** the stage job is `yes`

#### Scenario: An item under the limit
- **WHEN** 2 items are Planned, the setting is 3, and a Ready `P2-Medium` item passes every other rule
- **THEN** the stage job is `yes`

#### Scenario: The limit from the settings
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_STAGE_PLANNED_LIMIT` holds 1, 1 item is Planned, and a Ready `P2-Medium` item passes every other rule
- **THEN** the stage job is `no` with the reason of the limit

### Requirement: The command reports an item that the stage job holds for a retry
For the stage job, `devops roadmap explain <issue>` SHALL read `stage.failed_at`, `stage.failed_error` and `stage.failed_class` in the job record of the item on GitHub. When the failure is younger than the wait of its class (`RETRY_AFTER`, and `ci_infra` for a record with no class), the stage job SHALL be `no`, and the reason SHALL name the error class and the time after which the job takes the item again.

#### Scenario: A held item
- **WHEN** the job record of a Ready item holds a failure of 5 minutes ago with the error `RoadmapStageError` and the class `plan_defect`
- **THEN** the stage job is `no` and the reason names `RoadmapStageError` and the time 1 hour after the failure

#### Scenario: A held item with no class
- **WHEN** the job record of a Ready item holds a failure of 5 minutes ago with the error `AIClientError` and no class
- **THEN** the stage job is `no` and the reason names `AIClientError` and the time 1 hour after the failure

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

### Requirement: Explain names the plan pull request of a rejected item
`devops roadmap explain <issue>` SHALL print, for the stage job, the reason that the job gives for an item that holds a `stage.rejected` record, and the reason SHALL name the plan pull request that a person closed.

#### Scenario: A rejected item that is Ready again
- **WHEN** a Ready item holds a `stage.rejected` record for pull request 7, its text hashes as recorded and no named file changed
- **THEN** the stage job is `no` and the reason names pull request 7 and says what ends the leave-out

### Requirement: Explain names a refine job failure
For a New item whose last refine round recorded the next step `failed`, `explain` SHALL say that the refine job failed, with the failed check names, and that a body edit makes refine try again. For the next step `retry`, `explain` SHALL say that the job failed and that the next round tries again.

#### Scenario: A job failure at the limit
- **WHEN** a New item records `refine.next_step` as `failed` and `refine.failed_check` as `problem_statement`
- **THEN** the refine job is `no` and the reason names `problem_statement` and a body edit

#### Scenario: A retry
- **WHEN** a New item records `refine.next_step` as `retry`
- **THEN** the refine job is `yes`

### Requirement: Totals of the last implement run
The command SHALL report the token total, the seconds total, the repair-round count and the outcome counts of the last implement run of the item. The totals SHALL include the model events and the attempt events that the trace bound dropped.

#### Scenario: Totals of a fixture run
- **WHEN** the job record of the fixture item holds a trace with one model event of 1200 input tokens, 300 output tokens and 90 seconds, and two attempt events, the first with outcome `failed` and next `repair`, the second with outcome `passed` and next `stop`
- **THEN** the output reports 1500 tokens, 90 seconds, 1 repair round, 1 failed outcome and 1 passed outcome

#### Scenario: A long run
- **WHEN** the trace of the item holds 100 model events of 20,000 input tokens, 300 output tokens and 4 seconds each, 150 shell calls and a failed attempt, and the bound drops every model event
- **THEN** the output reports 2030000 tokens and 400.0 seconds, the totals of the full run, and `--json` gives the same values

#### Scenario: A trace with no dropped sums
- **WHEN** the trace holds `events` and `dropped` and no dropped sum, as a trace from before the sums
- **THEN** the trace decodes with no error, and the totals are the sums of the kept events

### Requirement: The JSON object gives the same totals
The command SHALL give the same totals as a JSON object when it runs with `--json`.

#### Scenario: The JSON object agrees with the text
- **WHEN** the command runs with `--json` on the fixture item
- **THEN** the JSON object holds `tokens_total` 1500, `seconds_total` 90, `repair_rounds` 1 and `outcomes` with 1 failed and 1 passed, and the text output holds the same values

### Requirement: Item with no recorded run
The command SHALL state that the item has no recorded implement run when the job record holds no trace, and SHALL give no totals.

#### Scenario: No trace in the record
- **WHEN** the job record of the fixture item holds no `implement.trace` value
- **THEN** the output states that the item has no recorded run and gives no totals, and the JSON object gives null for each total

### Requirement: Dropped events beside the totals
The command SHALL state the number of events that the trace bound dropped, beside the totals. When the trace holds a sum of its dropped events, the line SHALL say that the totals include them. Otherwise the line SHALL say that the totals leave them out.

#### Scenario: Trace with dropped events
- **WHEN** the trace of the fixture item reports 12 dropped events and a dropped sum
- **THEN** the output names 12 dropped events and says that the totals include them

#### Scenario: Trace with dropped events and no dropped sum
- **WHEN** the trace of the fixture item reports 12 dropped events and no dropped sum, as a trace from before the sums
- **THEN** the output names 12 dropped events and says that the totals leave them out

### Requirement: Explain names a refine failure wait
For a New item whose job record holds `refine.failed_at` younger than the wait of `refine.failed_class`, `devops roadmap explain <issue>` SHALL print that the refine job is `no`, and the reason SHALL name the time after which refine takes the item again.

#### Scenario: A held item
- **WHEN** a New item's refine round failed with a `provider` error at 12:00 UTC and the clock reads 12:10
- **THEN** the refine job is `no` and the reason names 13:00

### Requirement: The trace option prints the argument digest of a tool call
`explain <issue> --trace` SHALL show in the line of a `tool` event the digest of its argument, when the event holds one, so that a reader sees a repeated call. A `tool` event with no digest SHALL show no argument part.

#### Scenario: The same call twice
- **WHEN** the trace holds two `tool` events with the digest `abc123abc123`
- **THEN** each line says `[argument abc123abc123]`

#### Scenario: A tool call with no digest
- **WHEN** a `tool` event holds no digest
- **THEN** its line has no argument part
