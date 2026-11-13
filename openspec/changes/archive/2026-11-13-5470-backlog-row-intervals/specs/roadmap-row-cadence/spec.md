## Purpose
How often the Service runs the rows `intake`, `stage`, `fix_plan`, `refine` and `alternatives`: the interval of each row from its settings, and a shorter interval while the queue of the row holds a backlog, with the record, the log line and the gauges of that queue.

## ADDED Requirements

### Requirement: Each row reads its interval from its settings at each round
The rows `intake`, `stage`, `fix_plan`, `refine` and `alternatives` SHALL be due by the interval of `roadmap.<row>.interval_minutes`, which a round SHALL read from the settings at its start. The defaults SHALL be 29, 37, 53, 17 and 719 minutes. The section `roadmap.refine` SHALL hold the settings of the refine row. A variable SHALL set each setting, such as `DEVOPS_CLI_ROADMAP_STAGE_INTERVAL_MINUTES`. A setting below 1 SHALL stop the settings from loading.

#### Scenario: The defaults are the old intervals
- **WHEN** A test loads the settings with no source that sets a cadence.
- **THEN** `interval_minutes` is 29 for intake, 37 for stage, 53 for fix_plan, 17 for refine and 719 for alternatives, and `backlog_interval_minutes` and `backlog_threshold` are empty in each section.

#### Scenario: A variable changes the interval of the next round
- **WHEN** A test sets `DEVOPS_CLI_ROADMAP_STAGE_INTERVAL_MINUTES` to 20 and runs a dry round 20 minutes and 19 minutes after the last success of stage.
- **THEN** The round at 20 minutes lists stage, and the round at 19 minutes does not.

### Requirement: A backlog makes a row due at its backlog interval
While the queue that the last round of a row recorded holds `roadmap.<row>.backlog_threshold` or more items, the row SHALL be due at `roadmap.<row>.backlog_interval_minutes`. A queue below the threshold, a row with no recorded queue, and a section in which one of the two settings is empty SHALL keep `interval_minutes`. The settings SHALL refuse a `backlog_interval_minutes` above `interval_minutes`.

#### Scenario: A queue at the threshold uses the backlog interval
- **WHEN** The record holds a stage queue of 50, the threshold is 50 and the backlog interval is 13 minutes, and a test runs a dry round 13 minutes and 12 minutes after the last success of stage.
- **THEN** The round at 13 minutes lists stage, and the round at 12 minutes does not.

#### Scenario: A queue below the threshold keeps the interval
- **WHEN** The record holds a stage queue of 49 with the same settings, and a test runs a dry round 36 minutes and 37 minutes after the last success of stage.
- **THEN** The round at 36 minutes does not list stage, and the round at 37 minutes lists it.

#### Scenario: A backlog interval above the interval is refused
- **WHEN** A test sets `roadmap.stage.backlog_interval_minutes` to 40 while `roadmap.stage.interval_minutes` is 37.
- **THEN** The settings raise a validation error that names `backlog_interval_minutes`.

### Requirement: Each runner gives its queue from the listing of its round
The runner of each of the five rows SHALL give the size of its queue in `JobOutcome.queue`, counted from the listings that its round reads, and SHALL send no request for the count. A runner that reads no listing, such as `fix_plan` in the mode `off`, SHALL give None.

#### Scenario: The fix_plan row in the mode off gives no queue
- **WHEN** `roadmap.fix_plan.mode` is `off` and the fix_plan runner runs.
- **THEN** Its outcome holds no queue.

### Requirement: The queue of each row
The queue SHALL be: for `intake`, the candidates of the round (decided, left and held); for `stage`, the open items that the stage filter names; for `fix_plan`, the open pull requests of the issue listing that hold `plan/needs-fix`; for `refine`, the items that the selection orders before the rules of each item and the limit; for `alternatives`, the items that the check can take and has not checked.

#### Scenario: The stage selection counts the items that the filter names
- **WHEN** The store holds 4 open Ready items and the stage limit is 1.
- **THEN** The selection takes 1 item and its queue is 4.

#### Scenario: The refine selection counts the items that it orders
- **WHEN** The store holds 3 New items that refine can take and the limit is 1.
- **THEN** The selection takes 1 item and the queue of the plan is 3.

#### Scenario: The store counts the plans with the label from its listing
- **WHEN** The store holds 2 open pull requests with `plan/needs-fix`, 1 closed pull request with it and 1 open pull request without it.
- **THEN** `labelled_pulls("plan/needs-fix")` gives the 2 open ones.

### Requirement: The round keeps the last queue of each row
When a row with a cadence succeeds and its outcome holds a queue, the round SHALL write the queue to `queues.json` beside `schedule.json` and keep the queues of the other rows. A failed row and an outcome with no queue SHALL keep the last record. A `queues.json` that exists and cannot be read SHALL stop the round with `RoadmapRunError` that names the file, and no row SHALL run.

#### Scenario: A success records the queue
- **WHEN** A stage row that gives a queue of 177 succeeds in a round.
- **THEN** `queues.json` holds `{"stage": 177}`, and the next round uses the queue of 177.

#### Scenario: An unreadable record stops the round
- **WHEN** A test writes `{not json` to `queues.json` and runs a due round of a table with a stage row.
- **THEN** The round raises `RoadmapRunError` that names the file, and no row runs.

### Requirement: The round logs and sends the queue and the interval in use
After a row with a cadence succeeds and gives its queue, the round SHALL log one line that names the row, the repository, the queue and the minutes of the interval that the next round uses, and that names the threshold while the backlog rule applies. It SHALL send the gauge `devops_cli_roadmap_row_queue_items` with the queue and the gauge `devops_cli_roadmap_row_interval_seconds` with that interval in seconds, both with the attributes `repo` and `row`.

#### Scenario: A backlog round logs and sends the backlog interval
- **WHEN** The stage threshold is 50 and the backlog interval is 13 minutes, and a stage row that gives a queue of 177 succeeds.
- **THEN** The log names stage, the repository, 177 items, 13 minutes and the threshold 50, and the gauges hold 177 and 780 under `repo` and `row` `stage`.

### Requirement: The registry lists the gauges of the cadence
`INSTRUMENTS` SHALL hold `devops_cli_roadmap_row_queue_items` as a gauge with the unit `1` and `devops_cli_roadmap_row_interval_seconds` as a gauge with the unit `s`, and `docs/TELEMETRY.md` SHALL list both.

#### Scenario: The registry and the document list the gauges
- **WHEN** A test reads `INSTRUMENTS` and `docs/TELEMETRY.md`.
- **THEN** Both list `devops_cli_roadmap_row_queue_items` and `devops_cli_roadmap_row_interval_seconds` as gauges.
