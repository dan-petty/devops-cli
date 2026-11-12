# sre-service-dashboard Specification

## Purpose
The generic service dashboard `k8s/monitoring/dashboards/devops-sre-service.json`, "Service: SLO and golden signals", which the template of `service-dashboard-template` builds, and the log series that its log panels show.

## Requirements

### Requirement: Loki discover_log_levels pinned
`k8s/logging/loki-values.yaml` SHALL set `discover_log_levels: true` under `loki.limits_config` with a comment naming the panel "Logs: warnings and errors" of the service dashboards.

#### Scenario: Verify Loki values
- **WHEN** the test reads `loki-values.yaml` and checks the `limits_config` section
- **THEN** the key `discover_log_levels` has value `true` under `loki.limits_config` and the comment names the panel

### Requirement: README dashboard entry
`k8s/README.md` SHALL list `devops-roadmap-service.json` and `devops-sre-service.json` in the ConfigMap `grafana-service-dashboards`, and SHALL tell that `make dashboards` builds them from `services.toml`.

#### Scenario: Verify README
- **WHEN** the test reads the section "Grafana Dashboards" of `k8s/README.md`
- **THEN** the row of `grafana-service-dashboards` lists both files and the section names `make dashboards`

### Requirement: The template builds the generic service dashboard
`k8s/monitoring/dashboards/devops-sre-service.json`, "Service: SLO and golden signals" (uid `devops-sre-service`), SHALL be the build of its spec in `services.toml` with the template of `service-dashboard-template`, with the variables `namespace` (default `devops`) and `workload` (default `roadmap-service`). No file `sre-service.json` SHALL exist.

#### Scenario: The generic spec
- **WHEN** the test reads the specs of `services.toml`
- **THEN** a spec has the uid `devops-sre-service` and its file is the build

### Requirement: The log row shows the warnings above all lines of the workload pods
The log row of a service dashboard SHALL hold "Logs: warnings and errors" (`h8`) above "Logs: all lines" (`h12`), on the `loki` data source. The query of all lines SHALL be `{namespace="<namespace>"} | pod=~"<workload>-[a-z0-9]+-[a-z0-9]+"`, and the warnings query SHALL add `| detected_level=~"(?i)(warn|warning|error|err|critical|fatal|panic)"`.

#### Scenario: The log row of a fixture build
- **WHEN** the test reads the panels of the row "Logs" of the build of the namespace `shop` and the workload `cart`
- **THEN** the two panels have these titles, queries and heights, in this order
