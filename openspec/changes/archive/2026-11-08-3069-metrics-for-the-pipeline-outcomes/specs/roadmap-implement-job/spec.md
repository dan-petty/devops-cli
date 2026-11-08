# Spec Delta

## ADDED Requirements

### Requirement: Implement job outcome counter
The roadmap Service SHALL increment `devops_cli_service_implement_jobs_total` with the labels `repo`, `item_class` and `result` once for each runner Job that a round reports.

#### Scenario: A reported runner Job counts once
- **WHEN** A round reports a runner Job for repository `owner/repo`, item class `feat` and result `succeeded`.
- **THEN** The series `devops_cli_service_implement_jobs_total{repo="owner/repo",item_class="feat",result="succeeded"}` increases by one.

### Requirement: Repair rounds counter
The roadmap Service SHALL increment `devops_cli_service_implement_repair_rounds_total` with the labels `repo` and `item_class` by the repair-round count of each reported implement step.

#### Scenario: Repair rounds add to the counter
- **WHEN** A reported implement step records two repair rounds for repository `owner/repo` and item class `feat`.
- **THEN** The series `devops_cli_service_implement_repair_rounds_total{repo="owner/repo",item_class="feat"}` increases by two.

### Requirement: Token counter
The roadmap Service SHALL increment `devops_cli_service_implement_tokens_total` with the labels `repo` and `item_class` by the token count that the reported runner Job records.

#### Scenario: Tokens add to the counter
- **WHEN** A reported runner Job for repository `owner/repo` and item class `feat` records 1,000 tokens.
- **THEN** The series `devops_cli_service_implement_tokens_total{repo="owner/repo",item_class="feat"}` increases by 1,000.

### Requirement: Consecutive-failure gauge
The roadmap Service SHALL expose `devops_cli_service_implement_consecutive_failures` with the labels `repo` and `class`, and the gauge SHALL hold the number of stops in a row of that class.

#### Scenario: A stop increments its class gauge
- **WHEN** A reported stop has class `tests` and the gauge for `tests` is 1.
- **THEN** The gauge `devops_cli_service_implement_consecutive_failures{repo="owner/repo",class="tests"}` becomes 2.

### Requirement: Consecutive-failure gauge persists
The roadmap Service SHALL keep the consecutive-failure gauge value in a state record and SHALL report the same value after a restart.

#### Scenario: A restart keeps the gauge value
- **WHEN** A Service stops with `devops_cli_service_implement_consecutive_failures{repo="owner/repo",class="tests"}` at 2 and a new Service starts from the same state record.
- **THEN** The new Service exposes the same gauge value 2.

### Requirement: Different class resets the earlier gauge
The roadmap Service SHALL set the consecutive-failure gauge of a class to zero when a stop of another class follows.

#### Scenario: A different class resets the earlier gauge
- **WHEN** The gauge for class `tests` is 2 and the next reported stop has class `timeout`.
- **THEN** The gauge for `tests` becomes 0 and the gauge for `timeout` becomes 1.

### Requirement: Delivered item resets the earlier gauge
The roadmap Service SHALL set the consecutive-failure gauge of a class to zero when a delivered item follows.

#### Scenario: A delivered item resets the earlier gauge
- **WHEN** The gauge for class `tests` is 2 and a runner Job reports a delivered item.
- **THEN** The gauge for `tests` becomes 0.

### Requirement: Repair rounds in the job record
The roadmap Service SHALL record the integer repair-round count of each implement step in the item job record from `StepOutcome.repair_rounds`.

#### Scenario: A step with repair rounds is recorded
- **WHEN** An implement step ends with two repair rounds.
- **THEN** The item job record holds the integer `2` for the step's repair-round count.
