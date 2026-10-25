# dashboard-aggregate-lines Specification

## Purpose
Workload sum and average reference queries on breakdown panels across repository Grafana dashboards.

## Requirements

### Requirement: Breakdown panels show properly wrapped sum and average lines
Each in-scope breakdown panel in `sre-service.json`, `ingress-tunnel.json`, `k8s-views-nodes.json`, `k8s-views-pods.json`, and `llm-stack.json` SHALL calculate `Total (Sum)` as `sum(<refId A query>)` and `Average (Mean)` as `avg(<refId A query>)`. A panel displaying percentages SHALL only calculate `Average (Mean)`.

#### Scenario: Aggregate lines wrap the breakdown query
- **WHEN** in-scope dashboard panels are loaded
- **THEN** every `Total (Sum)` target expression equals `sum(<refId A>)`
- **AND** every `Average (Mean)` target expression equals `avg(<refId A>)`
- **AND** the panel "GPU Utilisation" contains only `Average (Mean)`
- **AND** the panel "Calls in Flight per Deployment" contains both `Total (Sum)` and `Average (Mean)`

### Requirement: Aggregate lines have dashed reference line styling
Each aggregate line on an in-scope breakdown panel SHALL have a matching `byName` field override with dashed line style, width 2, and a fixed color. No aggregate line SHALL set a custom axis placement override.

#### Scenario: Overrides apply dashed styling and fixed color
- **WHEN** field configuration overrides on in-scope breakdown panels are checked
- **THEN** each aggregate line has an override matched by its display name
- **AND** `custom.lineStyle.fill` is `dash`
- **AND** `custom.lineWidth` is `2`
- **AND** `color.mode` is `fixed`
- **AND** no `custom.axisPlacement` property is configured
