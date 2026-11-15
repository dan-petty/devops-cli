## ADDED Requirements

### Requirement: The ingest WorkflowTemplate holds no absent endpoint
The rag-ingest WorkflowTemplate SHALL set no `OTEL_EXPORTER_OTLP_ENDPOINT`, because its mounted ConfigMap names `telemetry.endpoint`, and a `k8s` row of `devops ci` SHALL refuse an OTLP endpoint in `k8s/` that names a host in namespace `otel` other than `otel-collector-opentelemetry-collector`.

#### Scenario: The template names no endpoint variable
- **WHEN** a person reads WorkflowTemplate rag-ingest
- **THEN** its environment holds no `OTEL_EXPORTER_OTLP_ENDPOINT`, and its config volume names `devops-cli-config`, which holds `telemetry.endpoint`

#### Scenario: A wrong endpoint fails the k8s row
- **WHEN** a manifest under `k8s/` sets `OTEL_EXPORTER_OTLP_ENDPOINT` to a host in `otel.svc.cluster.local` other than the Collector Service
- **THEN** `devops ci --check --only k8s` fails and names the file and the host
