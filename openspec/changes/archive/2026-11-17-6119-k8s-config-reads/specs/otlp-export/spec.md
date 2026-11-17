## MODIFIED Requirements

### Requirement: The devops perimeter opens only OTLP/HTTP to the collector
The NetworkPolicy of the `devops` namespace SHALL allow egress to the `otel` namespace on TCP 4318 only, and not on the OTLP gRPC port, 4317.

#### Scenario: The devops egress rule to otel
- **WHEN** a person runs `kubectl -n devops get networkpolicy -o yaml` on the cluster
- **THEN** the egress rule whose peer is the `otel` namespace names the one port TCP 4318
