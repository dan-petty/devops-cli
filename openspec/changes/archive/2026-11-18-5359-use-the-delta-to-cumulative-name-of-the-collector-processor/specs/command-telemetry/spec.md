## MODIFIED Requirements

### Requirement: The collector deletes the host name of devops-cli metrics before it adds the deltas
The metrics pipeline of the OpenTelemetry collector SHALL run a transform processor after memory_limiter and before delta_to_cumulative that deletes the resource attribute host.name where telemetry.sdk.name is the SDK name of the tracer, so that an old and a new devops-cli build of one workload send one stream.

#### Scenario: The rule runs before the deltas are added
- **WHEN** The test reads the metrics pipeline of `k8s/otel/values.yaml` and the metric Resource that the tracer exports.
- **THEN** The processors before delta_to_cumulative are memory_limiter and transform/metric_resource, and transform/metric_resource deletes host.name from the resource where telemetry.sdk.name equals the exported SDK name.
