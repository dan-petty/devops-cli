## ADDED Requirements

### Requirement: The MCP server rolls with no gap
Deployment `devops/mcp-server` SHALL use the `RollingUpdate` strategy with `maxSurge: 1` and `maxUnavailable: 0`. Its readiness probe SHALL call the HTTP route `/healthz` of the server on port 8001.

#### Scenario: A release of the MCP server
- **WHEN** a test reads `k8s/devops/mcp-server/deployment.yaml`
- **THEN** the strategy is `RollingUpdate` with `maxSurge: 1` and `maxUnavailable: 0`, and the readiness probe is `httpGet` on `/healthz`, port 8001

### Requirement: The health route needs no token and gives no data
The HTTP app of `devops mcp serve --transport streamable-http` SHALL answer `GET /healthz` with 200 and `{"status": "ok"}` with no bearer token. The route SHALL run no tool.

#### Scenario: The kubelet calls the route
- **WHEN** a client with no token sends `GET /healthz`
- **THEN** the answer is 200 with `{"status": "ok"}`

#### Scenario: A tool call on the route
- **WHEN** a client posts a `tools/list` request to `/healthz`
- **THEN** the answer is 405, and no tool runs

### Requirement: A second gateway replica needs shared cooldowns and a disruption budget
Deployment `llm/llm-gateway` SHALL run more than one replica only when `router_settings.redis_host` shares the cooldowns of the router and a PodDisruptionBudget selects the gateway. With one replica, the gateway SHALL have no PodDisruptionBudget, and `k8s/README.md` SHALL give the reason for one replica.

#### Scenario: One replica
- **WHEN** a test reads the gateway Deployment, the gateway config and `k8s/README.md`
- **THEN** the Deployment has one replica, the router sets no `redis_host`, no PodDisruptionBudget selects the gateway, and the README gives the reason
