## ADDED Requirements

### Requirement: The monitoring perimeter reaches the site metrics port
NetworkPolicy `monitoring-default-perimeter` SHALL admit egress from the pods of namespace `monitoring` to namespace `danielpetty-com` on TCP 9090 only.

#### Scenario: The rendered egress rule
- **WHEN** a person runs `uv run devops ci --check --only k8s`
- **THEN** the command exits 0, and the namespace selector of the rule names `danielpetty-com`, which `k8s/namespaces.yaml` declares

#### Scenario: Alloy scrapes the event-stream
- **WHEN** the event-stream pod of the site serves its metrics on TCP 9090, and a person queries Prometheus for `up{namespace="danielpetty-com"}`
- **THEN** each series has the value 1
