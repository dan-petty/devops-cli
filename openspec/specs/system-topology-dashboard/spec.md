# system-topology-dashboard Specification

## Purpose
Provides system topology, distributed trace service map, autonomous brain decisions, and component health panels in Grafana.

## Requirements

### Requirement: The system topology dashboard shows network, service map, and brain panels
The system topology dashboard `k8s/monitoring/dashboards/system-topology.json` SHALL exist with uid `system-topology` and title `System Topology & Service Map`. It SHALL provide network, service map, and brain rows, including a Tempo `nodeGraph` panel. It SHALL be provisioned through ConfigMap `grafana-topology-dashboards`.

#### Scenario: The dashboard contains required rows and nodeGraph panel
- **WHEN** the dashboard `system-topology.json` is loaded
- **THEN** its uid is `system-topology` and its title is `System Topology & Service Map`
- **AND** it contains rows "Network & Ingress Topology", "Distributed Trace Service Map", and "Project Brain & Decision Flow"
- **AND** it contains a panel of type `nodeGraph` bound to the `tempo` datasource with `queryType: "serviceMap"`
- **AND** the ConfigMap `grafana-topology-dashboards` provisions `system-topology.json`

### Requirement: The system topology dashboard shows overview stat panels
The system topology dashboard SHALL provide a "System Overview" row with panels of type `stat`. These panels SHALL display tunnel connections, ingress request volume, AI gateway health, and autonomous brain decisions.

#### Scenario: The dashboard contains summary stat panels
- **WHEN** the dashboard `system-topology.json` is loaded
- **THEN** it contains a row titled "System Overview"
- **AND** it contains at least 4 panels of type `stat`

### Requirement: The system topology dashboard shows state timeline and status history panels
The system topology dashboard SHALL provide a "Component State & Status History" row. It SHALL contain at least one panel of type `state-timeline` and at least one panel of type `status-history` to track service availability and knowledge drift over time.

#### Scenario: The dashboard contains timeline and history panels
- **WHEN** the dashboard `system-topology.json` is loaded
- **THEN** it contains a row titled "Component State & Status History"
- **AND** it contains at least one panel of type `state-timeline`
- **AND** it contains at least one panel of type `status-history`
