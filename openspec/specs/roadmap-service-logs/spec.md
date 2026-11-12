# roadmap-service-logs Specification

## Purpose
Provides unified failure logging and error reporting for roadmap service jobs, retains git clone failures, and suppresses noisy tracebacks for configuration errors.

## Requirements

### Requirement: Configuration error handling in roadmap service
When a managed repository listed in `service.repos` lacks `.github/roadmap.toml`, `service_job` SHALL raise a `ConfigurationError` specifying the missing path and advising to commit the configuration or remove the repository.

#### Scenario: Missing roadmap configuration in service
- **WHEN** `service_job` executes for a repository lacking `.github/roadmap.toml`
- **THEN** it raises a `ConfigurationError` with `key="service.repos"` and `details={"path": ".github/roadmap.toml"}`

### Requirement: Unified job failure reporting with clone error retention
When roadmap jobs fail during execution, `run_due_jobs` SHALL raise a `RoadmapRunError` naming each failed job alongside the first line of its error, preserving clone errors and attaching an `ExceptionGroup` containing all member failures annotated with their job names.

#### Scenario: Multiple jobs fail including clone failure
- **WHEN** jobs fail due to a clone error and a job runner error
- **THEN** `RoadmapRunError` message names each job and error line capped at 256 characters, and `__cause__` is an `ExceptionGroup` containing each exception

### Requirement: Configuration-only failure traceback suppression in service logging
When a service job execution fails exclusively due to configuration errors, the service worker SHALL log a single ERROR record without `exc_info` containing the repository and error message. For any unexpected error, the worker SHALL log an ERROR record with full `exc_info`.

#### Scenario: Service logs configuration-only failure
- **WHEN** a service job execution raises a `ConfigurationError` or a `RoadmapRunError` containing only `ConfigurationError`s
- **THEN** the service logs one ERROR record without a traceback, recording `repo` and `result="error"`

#### Scenario: Service logs unexpected failure
- **WHEN** a service job execution raises an unexpected error or a mixed error group
- **THEN** the service logs an ERROR record with `exc_info=True` showing the exception traceback

### Requirement: CLI literal error printing on failed roadmap run
When `devops roadmap run --confirm` encounters a `RoadmapRunError`, it SHALL print the exception message literally using safe markup printing without tracebacks and exit with code 1.

#### Scenario: CLI run failure output
- **WHEN** `devops roadmap run --confirm` fails with a `RoadmapRunError`
- **THEN** the command prints the error message safely without evaluating Rich markup and exits with code 1

### Requirement: Service JSON log lines carry the ids of the open span
Each JSON line that the roadmap Service writes to stdout while a span is open SHALL carry the `trace_id` and `span_id` of that span: a span of the own tracer, else the current OpenTelemetry span. A line written with no open span SHALL carry neither key.

#### Scenario: A line written in a span of the own tracer
- **WHEN** a Service logger writes a record while a span of the own tracer is open
- **THEN** the JSON line carries the `trace_id` and `span_id` of the exported span

#### Scenario: A line written in an OpenTelemetry span
- **WHEN** a Service logger writes a record while only an OpenTelemetry SDK span is open
- **THEN** the JSON line carries that span's trace id as 32 hex characters and its span id as 16 hex characters

#### Scenario: A line written with no open span
- **WHEN** a Service logger writes a record with no open span
- **THEN** the JSON line has no `trace_id` key and no `span_id` key

### Requirement: Each fix round and each failed item logs one line with counts
The roadmap jobs SHALL log one line with counts and no model text for a stage reply that passes or stays refused after a return, for each stage review round, for each failed stage item with its step and class, and for each ended implement Job with its state, class, repair rounds, tokens and runner digest. Each line SHALL name the repository before the item, and SHALL end with the devops-cli version.

#### Scenario: A pass after a return and two review rounds
- **WHEN** the first review returns a plan, the checks refuse the revision once, and the next revision passes the checks and the review
- **THEN** two `stage review round` lines give the repository, the item, rounds 0 and 1 and their counts, and one `stage gate returns` line gives `returns=1 result=passed`

#### Scenario: A failed item
- **WHEN** a stage round fails an item whose plan the checks refused after each return
- **THEN** one `stage item failed` line gives the repository, the item, the step `plan` and the class `plan_defect`

#### Scenario: An implement attempt
- **WHEN** the implement row reports a Job that failed with an out-of-memory log on runner digest `sha256:<a>`
- **THEN** one `implement attempt` line gives the repository, the item, `state=failed class=oom` and that digest

### Requirement: The error line of a round names every failed item
The error line of a failed round SHALL keep the first 256 characters of the first line of each error, and then give the number of each failed item of an error that has failed items.

#### Scenario: A long reason of the first item
- **WHEN** the stage row fails three items and the first line of its error is longer than 256 characters
- **THEN** the error of the round ends with `(failed items: #1, #2, #3)`

### Requirement: Each roadmap job logs one result line for each attempt
The stage, implement, refine, refine judge, alternatives and intake jobs SHALL log one `roadmap job result` line for each attempt, with the job, repository, item, result, success, failure class, infrastructure flag, counts and version. A line SHALL hold numbers and fixed names only, never issue or model text.

#### Scenario: A stage round of three tried items
- **WHEN** a stage round stages one item, stops one on its budget, fails one after a gate return and leaves one out
- **THEN** three lines give `staged success=true`, `needs_split` and `failed class=plan_defect gate_returns=1`

#### Scenario: A killed implement Job
- **WHEN** the implement row reports a Job that the kernel killed for its memory after 1200 seconds
- **THEN** one line gives `result=stopped success=false class=oom infra=true seconds=1200`

#### Scenario: Issue text in a value
- **WHEN** a result or a name holds a space
- **THEN** the line holds `other` in its place
