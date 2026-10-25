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
