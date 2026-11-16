## ADDED Requirements

### Requirement: Kept work counts its outcome
The roadmap Service SHALL increment `devops_cli_service_kept_work_total` with the labels `repo`, `class` and `outcome`: `continued` and the class of the stop when it creates a runner Job for an item whose record holds kept work, `finished` when that Job reaches the ready mark, and `blocked` and the class of the new stop when it stops again. Each `class` SHALL be a member of `FailureClass`. It MUST NOT increment the counter for an item with no kept work.

#### Scenario: A next Job starts from kept work
- **WHEN** A clear rule takes an item whose record holds `implement.wip` and the class `parser` out of Blocked, and the next round creates its runner Job.
- **THEN** The record holds `implement.continued` with the class `parser`, and the series with the outcome `continued` and the class `parser` increases by one.

#### Scenario: Kept work reaches the ready mark
- **WHEN** A round reports a runner Job whose record holds `implement.continued` with the class `parser` and whose result is `ready`.
- **THEN** The series with the outcome `finished` and the class `parser` increases by one, `devops_cli_service_implement_jobs_total` increases by one only, the record clears `implement.continued`, and a second round adds nothing.

#### Scenario: Kept work stops again
- **WHEN** A round reports a runner Job whose record holds `implement.continued`, and its report finds the new stop with the class `oom`.
- **THEN** The series with the outcome `blocked` and the class `oom` increases by one, and the record clears `implement.continued`.

#### Scenario: An item with no kept work
- **WHEN** A round creates and reports a runner Job for an item whose record holds `implement.continued` and no `implement.wip`.
- **THEN** No series of the kept-work counter changes, the claim clears `implement.continued`, and `devops_cli_service_implement_jobs_total` increases by one.

#### Scenario: A yield or a return counts no outcome
- **WHEN** A round reports a runner Job whose record holds `implement.continued` and whose result is `yielded` or `returned`.
- **THEN** The record clears `implement.continued`, and no series of the kept-work counter changes.
