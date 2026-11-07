# sre-service-dashboard Specification

## Purpose
The panels of the SRE service dashboard `k8s/monitoring/dashboards/sre-service.json`, "SRE / Service Performance & Logs", and the log and telemetry series that each panel shows.

## Requirements

### Requirement: Two log panels in row 11
Row 11 SHALL hold two full-width logs panels on the `loki` datasource, with the top panel (id 21) at `h: 8, w: 24, x: 0, y: 39` and the lower panel (id 12) at `h: 12, w: 24, x: 0, y: 47`.

#### Scenario: Read dashboard JSON
- **WHEN** the test reads `sre-service.json` and inspects the panels in row 11
- **THEN** panel 21 has `gridPos` `{"h": 8, "w": 24, "x": 0, "y": 39}` and panel 12 has `gridPos` `{"h": 12, "w": 24, "x": 0, "y": 47}`, both with datasource uid `loki` and type `logs`

### Requirement: Top panel query and description
The top panel SHALL use the query `{namespace=~"$namespace"} | pod=~"$pod" | detected_level=~"(?i)(warn|warning|error|err|critical|fatal|panic)"` and its description SHALL mention namespace, pods, and Kubernetes Warning events.

#### Scenario: Verify top panel expr
- **WHEN** the test reads the expr field of panel 21's target and its description
- **THEN** the expr equals the lower panel's expr plus the level filter, and the description contains `namespace`, `pods`, and `Kubernetes Warning events`

### Requirement: Lower panel query and description
The lower panel SHALL use the query `{namespace=~"$namespace"} | pod=~"$pod"` and its description SHALL mention namespace and pods with no mention of a service.

#### Scenario: Verify lower panel expr
- **WHEN** the test reads the expr field of panel 12's target and its description
- **THEN** the expr is `{namespace=~"$namespace"} | pod=~"$pod"` and the description does not contain the word `service`

### Requirement: Row 18 and flamegraph positions
Row 18 SHALL be at `y: 59`, flamegraph 19 at `y: 60`, and flamegraph 20 at `y: 72`.

#### Scenario: Verify moved panels
- **WHEN** the test reads the `gridPos` of panels 18, 19, and 20
- **THEN** panel 18 has `y: 59`, panel 19 has `y: 60`, and panel 20 has `y: 72`

### Requirement: Loki discover_log_levels pinned
`k8s/logging/loki-values.yaml` SHALL set `discover_log_levels: true` under `loki.limits_config` with a comment naming the Warnings & Errors (Loki) panel.

#### Scenario: Verify Loki values
- **WHEN** the test reads `loki-values.yaml` and checks the `limits_config` section
- **THEN** the key `discover_log_levels` has value `true` under `loki.limits_config` and the comment names the panel

### Requirement: README dashboard entry
`k8s/README.md` SHALL give the dashboard its real title `SRE / Service Performance & Logs` and list both log panels.

#### Scenario: Verify README
- **WHEN** the test reads `k8s/README.md` at the dashboard entry
- **THEN** the title is `SRE / Service Performance & Logs` and both panel names appear
