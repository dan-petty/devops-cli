## ADDED Requirements

### Requirement: The devops-cli dashboard keeps the classic dashboard schema
The dashboard file `k8s/devops/dashboards/devops-cli.json` MUST hold a top-level `panels` array, MUST hold no `apiVersion` key, and MUST state the `schemaVersion` 42 that the Grafana 13 dashboards provisioned as files state, so that the classic file provider of the dashboard sidecar loads it.

#### Scenario: The dashboard file is classic JSON
- **WHEN** A test parses the devops-cli dashboard file as JSON
- **THEN** The object holds a top-level panels array, no apiVersion key, and the schema version 42
