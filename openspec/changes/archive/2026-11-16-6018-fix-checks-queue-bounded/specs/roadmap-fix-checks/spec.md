## MODIFIED Requirements

### Requirement: A fix Job goes first under the shared model limit
The implement, stage and fix-checks Jobs SHALL run at most `roadmap.model_jobs` at once (default 2), for every repository together. A fix Job with no free place SHALL be created suspended, and the watch row SHALL resume it first. A waiting fix Job SHALL hold its place against a new implement or stage Job only while the mode is not `off`, its repository is in `service.repos`, and it waited at most `roadmap.fix_checks.max_wait_minutes`.

#### Scenario: A waiting fix Job holds the place of a new implement Job
- **WHEN** `roadmap.model_jobs` is 1, a fix Job waits suspended, and an implement unit is due
- **THEN** the implement row creates no Job and waits

#### Scenario: A waiting fix Job holds the place of a new stage Job
- **WHEN** `roadmap.model_jobs` is 1, a fix Job waits suspended, and a Ready item is due for stage
- **THEN** the stage row creates no Job

#### Scenario: The watch row resumes the waiting fix Job
- **WHEN** a model Job ends while a fix Job of the repository waits suspended
- **THEN** the next round of the watch row resumes the fix Job and creates no other Job for its unit

#### Scenario: A waiting fix Job of a repository outside service.repos holds no place
- **WHEN** `service.repos` holds `example/project` and a fix Job of `example/other` waits suspended
- **THEN** `model_slots` counts no waiting Job, and a fix Job of `example/project` counts one

### Requirement: The watch row reports each ended fix Job once
The watch row SHALL read the result line of each ended fix Job once, log it as the result line of the job `fix_checks`, count it in `devops_cli_service_fix_checks_jobs_total`, and write it in the Job annotation `roadmap.devops-cli/outcome`. A Job with no result line SHALL have the outcome `deadline` when its deadline ended it, `error` when its command exited 1, and else `none`. The alert `RoadmapFixChecksJobWithoutResult` SHALL fire for each of the three.

#### Scenario: An ended Job is reported once
- **WHEN** a fix Job ends with the result line `planned` and the watch row runs twice
- **THEN** the first round logs and counts `planned` and writes the annotation, and the second round reports nothing

#### Scenario: A Job with no result line fires the alert
- **WHEN** the counter of the result `none`, `error` or `deadline` grows in the last hour
- **THEN** `RoadmapFixChecksJobWithoutResult` fires for the repository

#### Scenario: A Job that its deadline ended is deadline
- **WHEN** a fix Job ends with the condition reason `DeadlineExceeded` and no result line
- **THEN** the round reports and counts the outcome `deadline`

### Requirement: A fix Job with no result line gets the next attempt
When the last attempt of a unit has the outcome `none`, the watch row SHALL create the next attempt, named from `<pr>:<head>:<check>#<n>`, after a wait of 30 minutes doubled at each attempt up to 2 hours, and at most `roadmap.implement.continuations_per_item` attempts after the first. A Job with a result line, or with the outcome `error` or `deadline`, SHALL end its unit.

#### Scenario: The next attempt waits
- **WHEN** a fix Job ended with no result line
- **THEN** no Job is created before 30 minutes, and attempt 2 is created after them

#### Scenario: The attempts stop at the cap
- **WHEN** `roadmap.implement.continuations_per_item` is 1 and each attempt ends with no result line
- **THEN** the unit has 2 Jobs and no third

#### Scenario: A result line ends the unit
- **WHEN** the Job of a unit ended with a result line
- **THEN** the watch row creates no other Job for that head and check

#### Scenario: A Job that its deadline ended gets no next attempt
- **WHEN** the Job of a unit has the outcome `deadline`, and the watch row runs a day later
- **THEN** the watch row creates no other Job for that head and check

## ADDED Requirements

### Requirement: The item record keeps the attempts of a fix unit
In mode `on`, the watch row SHALL write the attempt, the outcome and the next allowed time of each fix Job that it reports in the item record `fix_checks.units`, keyed by `<pr>:<head>:<check>`, and a unit with no Job SHALL take its last attempt from that record, so the TTL of a Job resets nothing. Mode `plan` SHALL write no record.

#### Scenario: The attempt after the TTL is the next attempt
- **WHEN** in mode `on` attempt 1 of a unit ended with no result line, the TTL deleted it, and the unit is due a day later
- **THEN** the watch row creates attempt 2

#### Scenario: An error in the record ends the unit after the TTL
- **WHEN** in mode `on` the Job of a unit ended with the outcome `error` and the TTL deleted it
- **THEN** the watch row creates no Job for that unit

#### Scenario: Mode plan writes no unit record
- **WHEN** in mode `plan` the watch row reports an ended fix Job
- **THEN** the item record holds no `fix_checks.units`

### Requirement: One pull request has at most one live fix Job
The watch row SHALL create no Job for a unit of a pull request while a fix Job of that pull request runs or waits suspended. A unit of another check or another head of that pull request SHALL get its Job after that Job ends.

#### Scenario: A second failed check waits for the live Job
- **WHEN** the fix Job of the lint check of a head runs and a test shard of the same head fails
- **THEN** the round creates no Job, and it creates the Job of the shard after the lint Job ends with no repair

#### Scenario: A new head is a new unit
- **WHEN** the fix Job of the old head ended and the new head of the pull request fails a check
- **THEN** the round creates one Job for the new head

### Requirement: The watch row deletes a fix Job that waited too long
The watch row of any repository SHALL delete a fix Job that waited suspended longer than `roadmap.fix_checks.max_wait_minutes` (default 360), also a Job of a repository outside `service.repos`, and SHALL write a log line that names it. The policy `roadmap-service-job-deletes` SHALL admit the delete of a suspended fix-checks Job by the Service, and SHALL refuse the delete of a runner Job that runs.

#### Scenario: A fix Job past the wait limit is deleted
- **WHEN** a fix Job of `example/other` waited suspended one second longer than the limit, and the round of `example/project` runs
- **THEN** the round deletes it, logs one line that names it, and counts `expired`

#### Scenario: A fix Job within the wait limit stays
- **WHEN** a fix Job waited suspended exactly the limit
- **THEN** the round deletes nothing

#### Scenario: The policy admits only the delete of a waiting fix Job
- **WHEN** the Service deletes a stage Job, a suspended fix-checks Job, a fix-checks Job that runs, and a runner Job
- **THEN** the policy admits the first two and refuses the last two

### Requirement: The ready path of the step needs no repair
With `ready_only`, the step `fix-checks` SHALL run only its ready path: a head with a failed check SHALL give `skipped`, with no repair, no comment, no ready mark and no record.

#### Scenario: A check that fails after the read of the watch row
- **WHEN** the step runs with `ready_only` and `--confirm` on a repaired draft whose head has a failed check, of the class lint or `ci_infra`
- **THEN** the step gives `skipped`, posts no comment and marks nothing ready

### Requirement: The fix-checks panel draws 3 series and Other
The panel `Service Fix-Checks Jobs by Result` SHALL draw one series for each of Started (created, resumed), Repaired (repaired, ready) and No result line (none, error, deadline), and one series Other for each other result, each with a fixed legend.

#### Scenario: The panel has 4 fixed series
- **WHEN** the dashboard `roadmap-service-telemetry` is read
- **THEN** the panel has the targets Started, Repaired, No result line and Other, and no legend that names a label
