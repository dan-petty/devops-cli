## MODIFIED Requirements

### Requirement: Loki ingests patterns
The logging stack SHALL set `loki.pattern_ingester.enabled: true` in `k8s/logging/loki-values.yaml`, and SHALL keep pattern persistence off. A render of the chart that the Application `loki` pins, with those values, SHALL write `pattern_ingester` with `enabled: true` into the Loki configuration.

#### Scenario: The rendered configuration
- **WHEN** `helm template` renders `grafana-community/loki` at the `targetRevision` of the Application `loki` with `k8s/logging/loki-values.yaml`
- **THEN** the Loki configuration holds `pattern_ingester.enabled: true`

#### Scenario: No new pod
- **WHEN** the logging stack is applied
- **THEN** the pattern ingester runs in the existing Loki pod and adds no egress
