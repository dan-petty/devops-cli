## ADDED Requirements

### Requirement: Kept work counts its outcome
The roadmap Service SHALL increment `devops_cli_service_implement_jobs_total` with the result `continued` and the class of the stop when it creates a runner Job for an item whose record holds kept work. It SHALL increment it with `finished` when that Job reaches the ready mark, and with `blocked` and the class of the new stop when it stops again. It MUST NOT increment it with those three results for an item with no kept work.

#### Scenario: A next Job starts from kept work
- **WHEN** A clear rule takes an item whose record holds kept work out of Blocked, and the next round creates its runner Job.
- **THEN** The record holds `implement.continued` with the class of that stop, and the series with the result `continued` and that class increases by one.

#### Scenario: Kept work reaches the ready mark
- **WHEN** A round reports a runner Job whose record holds `implement.continued` with the class `parser` and whose result is `ready`.
- **THEN** The series with the result `finished` and the class `parser` increases by one, the record clears `implement.continued`, and a second round adds nothing.

#### Scenario: Kept work stops again
- **WHEN** A round reports a runner Job whose record holds `implement.continued`, and its report finds the new stop with the class `oom`.
- **THEN** The series with the result `blocked` and the class `oom` increases by one, and the record clears `implement.continued`.

#### Scenario: An item with no kept work
- **WHEN** A round creates and reports a runner Job for an item whose record holds no kept work.
- **THEN** No series of the counter holds the result `continued`, `finished` or `blocked` for that item, and the series with the result `succeeded` and the class `none` increases by one.

## MODIFIED Requirements

### Requirement: Implement job outcome counter
The roadmap Service SHALL increment `devops_cli_service_implement_jobs_total` with the labels `repo`, `item_class`, `result` and `class` once for each runner Job that a round reports. The `result` SHALL be `failed` when the report finds a failure class, and the state of the Job (`succeeded`, `failed` or `gone`) otherwise. The `class` SHALL be the failure class that the increment counts, or `none` when it counts none.

#### Scenario: A reported runner Job counts once
- **WHEN** A round reports a runner Job for repository `owner/repo` and item class `feat` that ended Complete with the result `ready`.
- **THEN** The series `devops_cli_service_implement_jobs_total{repo="owner/repo",item_class="feat",result="succeeded",class="none"}` increases by one.

#### Scenario: A stop that the runner wrote before it exited 0
- **WHEN** A round of `example/app` reports a runner Job that ended Complete, and its item holds the stop with the class `parser`.
- **THEN** The series with `result` `failed` and `class` `parser` increases by one, the series with `result` `succeeded` does not change, the failures counter for `parser` and `example/app` increases by one, and a second round adds nothing.
