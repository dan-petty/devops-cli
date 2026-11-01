# roadmap-explain Specification

## Purpose
How `devops roadmap explain` tells a person or an agent, for one roadmap issue, whether the stage job and the implement job take it, and the first rule that stops each job when they do not.

## ADDED Requirements

### Requirement: The command names the first rule that stops each job
`devops roadmap explain <issue>` SHALL print, for the stage job and for the implement job, `yes` or `no`. For `no` it SHALL print the reason of the first rule that fails. The rules and their order SHALL be those of the job. The reasons SHALL be the texts of the "Left out" list of `stage --plan` and `implement --plan`. The rules are not an item or closed, the filter, and the rules of the job, then the limit of a run.

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
- **THEN** both jobs are `no` and the reason says that it is closed or that it is no item

#### Scenario: The limit of a run
- **WHEN** an item passes every rule and the limit of a run is filled by items of higher priority
- **THEN** the job is `no` and the reason names the limit

#### Scenario: An item the job takes
- **WHEN** an item passes every rule within the limit
- **THEN** the job is `yes`

### Requirement: The command makes no model call and no write
`explain` SHALL call no model, SHALL write nothing to GitHub or to git, and SHALL change no label, comment or record. It SHALL read the issues, the branches and the change folders that the plan of the job reads.

#### Scenario: A read-only run
- **WHEN** `explain` runs with a model client that fails the test when it is built and a store that records writes
- **THEN** the exit status is 0 and the store records no write

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
