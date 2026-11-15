# Proposal: #5169

## Why

Roadmap jobs write one result line for each attempt (`roadmap job result:`).
`OTelLoggingHandler` previously filtered out records below WARNING level.
When the root logger is set to WARNING, the result lines of roadmap jobs are dropped and not exported to OpenTelemetry.
Local runs and Job pods that use the telemetry bridge therefore send no result lines to Loki.
Closes #5169.

## What Changes

- Configure `devops_cli.roadmap.job_result` logger to log at INFO level.
- Configure `OTelLoggingHandler` to accept records from `devops_cli.roadmap.job_result` at INFO level, while keeping WARNING level as the minimum for records from other loggers.
- Ensure the handler's internal level passes INFO records to `emit()` so that root logger level does not filter them during handler dispatch.

## Capabilities

- `roadmap-service-logs`: Roadmap job result lines export through the OpenTelemetry logging bridge.

## Impact

- SDLC, Git & PR Governance (`src/devops_cli/roadmap/job_result.py`, `src/devops_cli/telemetry/logging_bridge.py`).
- No breaking API changes; telemetry bridge captures job result lines at INFO while preserving WARNING threshold for other loggers.

## Feasibility

- The logger `devops_cli.roadmap.job_result` writes with `logger.info`.
- Setting `logger.setLevel(logging.INFO)` ensures `logger.isEnabledFor(logging.INFO)` evaluates to `True`.
- Setting the handler's level to INFO and filtering non-result-line loggers in `emit` allows result lines through while preserving WARNING filtering for all other loggers.

## Existing Tool Considered

OpenTelemetry logging handler already bridges standard library logging to OTLP. No new tool is required.
