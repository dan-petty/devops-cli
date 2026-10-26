# Spec Delta

## ADDED Requirements

### Requirement: A gauge reaches Prometheus through one path
Each gauge that devops-cli sends SHALL reach Prometheus through one path: through OTLP export, or through a Prometheus scrape endpoint, and never through both. No gauge sent over OTLP SHALL be registered or recorded in an in-memory Prometheus metrics registry or exposed by a Prometheus scrape endpoint.

#### Scenario: Two paths send the same gauge name
- **WHEN** an instrument sent over OTLP as a gauge has the same name as a gauge recorded in an in-memory Prometheus registry or exposed by a Prometheus scrape endpoint
- **THEN** the telemetry invariant check fails and names the shared gauge names
