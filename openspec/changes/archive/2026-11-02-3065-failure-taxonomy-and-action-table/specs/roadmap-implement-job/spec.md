## ADDED Requirements

### Requirement: The stop comment names the failure class
The stop comment of the job SHALL name the failure class, the action taken and the action left, before the reason. The job SHALL record the class in `implement.failure` with `implement.stopped`, and SHALL write one line with the class and the action left to its log. A retry of a person and a clear rule of the Service SHALL remove `implement.failure` with `implement.stopped`.

#### Scenario: A step that changed no file
- **WHEN** the step of group 2 stops with the reason "The agent changed no file."
- **THEN** the comment holds `Failure class: `plan_defect`.`, `Action taken: none.` and the action left `amend`, `implement.failure` is `plan_defect`, and the log of the job holds the class and `amend`

#### Scenario: Fix rounds that did not pass a check
- **WHEN** the scoped check `pre-push` fails after 3 fix rounds and its log names `ruff`
- **THEN** the comment holds the class `lint`, the action taken `repair` with 3 rounds, and the action left `wait`

#### Scenario: A retry
- **WHEN** a trusted person comments `implement: retry` on a stopped item and the job takes it
- **THEN** `implement.failure` is removed with `implement.stopped`

### Requirement: The Service counts the failures by class
When a round reports a Job that left a stop, the Service SHALL add 1 to `devops_cli_service_implement_failures_total` with the label `class`. A Job that left the item without a result SHALL get the class of the tail of its log, recorded in `implement.failure` and named, with the action left, in the report. A Job that ended with a result SHALL add nothing.

#### Scenario: A stop of the runner
- **WHEN** a round reports a Job whose item holds the stop with the class `parser`
- **THEN** the counter for `parser` grows by 1, the counter for `oom` does not change, and a second round adds nothing

#### Scenario: A Job with no result
- **WHEN** a round reports a Job that failed and left the item In Progress, and its log holds "out of memory"
- **THEN** the item is Blocked with `implement.failure` `oom`, the report names the class and the action left `raise_limit`, and the counter for `oom` grows by 1

#### Scenario: A Job with a result
- **WHEN** a round reports a Job that succeeded and left the item In Review
- **THEN** no counter changes
