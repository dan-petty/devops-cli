## MODIFIED Requirements

### Requirement: Breakdown panels show properly wrapped sum and average lines
Each in-scope breakdown panel in `ingress-tunnel.json`, `k8s-views-nodes.json` and `k8s-views-pods.json` SHALL calculate `Total (Sum)` as `sum(<refId A query>)` and `Average (Mean)` as `avg(<refId A query>)`. A panel displaying percentages SHALL only calculate `Average (Mean)`.

#### Scenario: Aggregate lines wrap the breakdown query
- **WHEN** in-scope dashboard panels are loaded
- **THEN** every `Total (Sum)` target expression equals `sum(<refId A>)`
- **AND** every `Average (Mean)` target expression equals `avg(<refId A>)`
