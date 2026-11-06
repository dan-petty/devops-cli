## MODIFIED Requirements

### Requirement: The Service counts the failures by class
When a round reports a Job that left a stop, the Service SHALL add 1 to `devops_cli_service_implement_failures_total` with the labels `class` and `repo`, where `repo` is the repository of the round. A Job that left the item without a result SHALL get the class of the tail of its log, recorded in `implement.failure` and named, with the action left, in the report. A Job that ended with a result SHALL add nothing.

#### Scenario: A stop of the runner
- **WHEN** a round of `example/app` reports a Job whose item holds the stop with the class `parser`
- **THEN** the counter for `parser` and `example/app` grows by 1, the counter for `oom` does not change, and a second round adds nothing

#### Scenario: A Job with no result
- **WHEN** a round of `example/app` reports a Job that failed and left the item In Progress, and its log holds "out of memory"
- **THEN** the item is Blocked with `implement.failure` `oom`, the report names the class and the action left `raise_limit`, and the counter for `oom` and `example/app` grows by 1

#### Scenario: A Job with a result
- **WHEN** a round reports a Job that succeeded and left the item In Review
- **THEN** no counter changes
