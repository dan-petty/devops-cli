# Spec Delta

## ADDED Requirements

### Requirement: The gateway status reports the routes in failover
`devops ai gateway status` SHALL name each virtual model whose route is a `failover:*` route, in the field `failover_routes` of its JSON and in a `Failover routes:` line of its table, and SHALL report the circuit breaker as tripped while such a route exists, also after a healthy probe of the gateway. A probe of the gateway SHALL NOT change a `failover:*` route.

#### Scenario: A healthy probe after a failover
- **WHEN** `devops-chat` fails over on a new route table, and then a probe of the gateway is healthy
- **THEN** the status is healthy, its circuit breaker is tripped, its `failover_routes` is `["devops-chat"]`, and the route table keeps the route of `devops-chat` to `qwen3.8:27b` with the backend type `failover:ollama`

#### Scenario: The table names the routes in failover and the reset
- **WHEN** `devops-chat` fails over, and then `devops ai gateway status` runs against a healthy gateway
- **THEN** its table contains `Failover routes: devops-chat` and names `--reset`, and the command exits 0

### Requirement: A failover reset restores the default routes
`devops ai gateway failover --reset` and the MCP tool `ai_gateway_failover` with `reset` SHALL write the default route of every virtual model to the route table, clear the circuit breaker, and name the virtual models that were in failover. A reset SHALL write the route table also when `--simulate` is given. The command SHALL refuse a reset with a virtual model, and a call with neither a virtual model nor `--reset`, as a usage error.

#### Scenario: A reset after a failover
- **WHEN** a route table holds a route that is not a default route, `devops-reasoning` fails over, and then a reset runs
- **THEN** the reset reports `restored_routes` `["devops-reasoning"]` and no tripped circuit breaker, and the route file holds the default routes and no tripped circuit breaker

#### Scenario: The MCP tool resets
- **WHEN** `devops-chat` fails over, and then the MCP tool `ai_gateway_failover` runs with `reset` and its default `simulate`
- **THEN** the route file holds the default routes and no tripped circuit breaker

#### Scenario: A reset with a virtual model
- **WHEN** `devops ai gateway failover devops-chat --reset` runs, or `devops ai gateway failover` runs with no virtual model and no `--reset`
- **THEN** the command exits 2
