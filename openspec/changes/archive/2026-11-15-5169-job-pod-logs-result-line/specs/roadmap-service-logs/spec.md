## ADDED Requirements

### Requirement: Roadmap job result lines export through the OpenTelemetry logging bridge
The `devops_cli.roadmap.job_result` logger SHALL log at INFO level. The OpenTelemetry logging handler SHALL export records from `devops_cli.roadmap.job_result` at INFO level, while keeping WARNING level as the minimum for records from other loggers.

#### Scenario: Job result line exported when root logger is at WARNING
- **WHEN** the root logger is configured at WARNING level and a roadmap job result line is logged
- **THEN** the OpenTelemetry logging handler receives the record and exports it to OTLP

#### Scenario: Other INFO log records are not exported
- **WHEN** a logger other than `devops_cli.roadmap.job_result` logs a record at INFO level while the handler is at WARNING level
- **THEN** the record is not exported to OTLP
