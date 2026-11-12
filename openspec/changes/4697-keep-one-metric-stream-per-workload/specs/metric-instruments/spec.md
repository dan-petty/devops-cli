## ADDED Requirements

### Requirement: The metric resource carries only stable attributes
The metric Resource of every devops-cli process SHALL contain only service.name, service.namespace, service.instance.id, os.type and the telemetry.sdk.* attributes.

#### Scenario: Two tracers with one instance send equal metric resources
- **WHEN** Two tracers start with different platform.node() values and the same OTEL_RESOURCE_ATTRIBUTES service.instance.id.
- **THEN** Their metric Resources are equal, and no key of a metric Resource is outside the allowed set.

### Requirement: The metric resource reads the configured instance
The metric Resource SHALL take service.instance.id from OTEL_RESOURCE_ATTRIBUTES when that variable sets it.

#### Scenario: A process with a fixed instance
- **WHEN** A tracer starts with OTEL_RESOURCE_ATTRIBUTES set to service.instance.id=devops-cli-job.
- **THEN** The metric Resource holds service.instance.id=devops-cli-job.

### Requirement: One cluster Job writes a metric stream at a time
Both cluster CronJob templates SHALL set OTEL_RESOURCE_ATTRIBUTES to service.instance.id=devops-cli-job, and a Job of the workload SHALL NOT be created while another Job of the workload has not ended.

#### Scenario: The templates set one instance
- **WHEN** A test reads both CronJob templates of the devops namespace.
- **THEN** Each container has OTEL_RESOURCE_ATTRIBUTES with the value service.instance.id=devops-cli-job.

#### Scenario: A second Job of the workload waits
- **WHEN** A round of the implement row, or the command `devops k8s run-job`, would create a Job while a Job of the workload has not ended.
- **THEN** The round reports that it waits, and `devops k8s run-job` refuses with the name of the running Job, so one pod of the workload writes the stream.
