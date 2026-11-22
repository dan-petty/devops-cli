## MODIFIED Requirements

### Requirement: Only the gateway and the operator reach the database
Policy `llm-gateway-db-perimeter-ingress` SHALL admit to the database pods on 5432 only the gateway's pods and the CloudNativePG operator (which also uses 8000). It SHALL admit namespace `monitoring` on the metrics port 9187 only, and the egress of policy `llm-gateway-db-perimeter-egress` SHALL be DNS and the Kubernetes API only. The gateway's egress policy SHALL admit egress to the database pods on 5432 by pod selector. `llm-default-perimeter-ingress` and `llm-default-perimeter-egress` SHALL leave the database pods out.

#### Scenario: The database perimeter
- **WHEN** `uv run devops ci --check --only k8s` runs
- **THEN** the row passes only when `llm-gateway-db-perimeter-ingress` and `llm-gateway-db-perimeter-egress` select the pods with `cnpg.io/cluster: llm-gateway-db`, the ingress policy admits the pods of `llm-gateway` on 5432, namespace `cnpg-system` on 8000 and 5432 and namespace `monitoring` on 9187, and the egress policy allows egress only on ports 53, 443 and 6443

#### Scenario: The gateway reaches the database by label
- **WHEN** `uv run devops ci --check --only k8s` runs
- **THEN** the row passes only when exactly one egress rule of `llm-gateway-perimeter-egress` names TCP 5432, with a pod selector on `cnpg.io/cluster: llm-gateway-db` as its peer

#### Scenario: The default perimeter leaves the database out
- **WHEN** `uv run devops ci --check --only k8s` runs
- **THEN** the row passes only when the pod selector of `llm-default-perimeter-ingress` and of `llm-default-perimeter-egress` excludes the pods with `cnpg.io/cluster: llm-gateway-db`

### Requirement: Alloy scrapes the metrics exporter of the gateway database
`k8s/llm/gateway-db.yaml` SHALL hold PodMonitor `llm-gateway-db` in namespace `llm`, which selects the pods with `cnpg.io/cluster: llm-gateway-db` on their port `metrics`. k8s-monitoring SHALL read PodMonitors, and the egress of `monitoring-default-perimeter-egress` to namespace `llm` SHALL admit TCP 9187.

#### Scenario: The PodMonitor and the egress
- **WHEN** a person runs `uv run devops prometheus query 'cnpg_collector_up{namespace="llm"}'`
- **THEN** the query returns the value 1 for the pod `llm-gateway-db-1`
- **AND** `uv run devops ci --check --only k8s` passes only when the PodMonitor selects `cnpg.io/cluster: llm-gateway-db` on the port `metrics`, k8s-monitoring reads PodMonitors, and the monitoring perimeter admits egress to namespace `llm` on TCP 9187
