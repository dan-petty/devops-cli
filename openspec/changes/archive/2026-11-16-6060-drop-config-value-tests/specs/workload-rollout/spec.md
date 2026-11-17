## MODIFIED Requirements

### Requirement: The MCP server rolls with no gap
Deployment `devops/mcp-server` SHALL use the `RollingUpdate` strategy with `maxSurge: 1` and `maxUnavailable: 0`. Its readiness probe SHALL call the HTTP route `/healthz` of the server on port 8001.

#### Scenario: A release of the MCP server
- **WHEN** a release of the MCP server rolls out, and a person runs `kubectl -n devops rollout status deployment/mcp-server`
- **THEN** the rollout completes, the old pod serves until the new pod is ready, and the new pod is ready only after its `httpGet` probe on `/healthz`, port 8001, answers

### Requirement: A second gateway replica needs shared cooldowns and a disruption budget
Deployment `llm/llm-gateway` SHALL run more than one replica only when `router_settings.redis_host` shares the cooldowns of the router and a PodDisruptionBudget selects the gateway. With one replica, the gateway SHALL have no PodDisruptionBudget, and `k8s/README.md` SHALL give the reason for one replica.

#### Scenario: One replica
- **WHEN** a person runs `kubectl -n llm get deploy,pdb` on the cluster
- **THEN** Deployment `llm-gateway` has one replica, no PodDisruptionBudget selects the gateway, the router sets no `redis_host`, and the README gives the reason
