## ADDED Requirements

### Requirement: The ingest template takes its OTLP endpoint from the ConfigMap
The rag-ingest WorkflowTemplate SHALL set no `OTEL_EXPORTER_OTLP_ENDPOINT`, because its mounted ConfigMap names `telemetry.endpoint`.

#### Scenario: The template names no endpoint variable
- **WHEN** a person runs `kubectl kustomize k8s/devops` and reads WorkflowTemplate `rag-ingest`
- **THEN** its environment holds no `OTEL_EXPORTER_OTLP_ENDPOINT`, and its config volume names `devops-cli-config`, which holds `telemetry.endpoint`

## REMOVED Requirements

### Requirement: The ingest WorkflowTemplate holds no absent endpoint
**Reason**: The `k8s` row has no check of OTLP endpoints (#7290).
**Migration**: See `The ingest template takes its OTLP endpoint from the ConfigMap`.
