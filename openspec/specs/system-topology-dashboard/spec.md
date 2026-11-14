# system-topology-dashboard Specification

## Purpose
Provides interactive system topology, distributed trace service map, and autonomous brain decision telemetry in Grafana.

## Requirements

### Requirement: The system topology dashboard shows network, service map, and brain panels
The system topology dashboard `k8s/monitoring/dashboards/system-topology.json` SHALL exist with uid `system-topology` and title `System Topology & Service Map`. It SHALL provide network, service map, and brain rows, including a Tempo `nodeGraph` panel. It SHALL be provisioned through ConfigMap `grafana-topology-dashboards`.

#### Scenario: The dashboard contains required rows and nodeGraph panel
- **WHEN** the dashboard `system-topology.json` is loaded
- **THEN** its uid is `system-topology` and its title is `System Topology & Service Map`
- **AND** it contains rows "Network & Ingress Topology", "Distributed Trace Service Map", and "Project Brain & Decision Flow"
- **AND** it contains a panel of type `nodeGraph` bound to the `tempo` datasource with `queryType: "serviceMap"`
- **AND** the ConfigMap `grafana-topology-dashboards` provisions `system-topology.json`
