## ADDED Requirements

### Requirement: The monitoring perimeter admits the SearXNG metrics scrape
The `monitoring-default-perimeter-egress` NetworkPolicy SHALL admit namespace `devops` to TCP port 8080 beside port 8000, so that a scrape of the SearXNG pod leaves the monitoring namespace.

#### Scenario: The k8s check accepts the new egress port
- **WHEN** `uv run devops ci --check --only k8s` runs on the branch that changes `k8s/monitoring/networkpolicy.yaml`
- **THEN** the check exits 0 and reports no error for `k8s/monitoring/networkpolicy.yaml`
