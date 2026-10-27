# Spec Delta

## ADDED Requirements

### Requirement: A saved route table keeps only failover state
The saved route table in `<data dir>/agent/gateway_state.json` SHALL keep only routes whose `backend_type` begins with `failover:`. When loading the route table, every non-failover route SHALL be taken from `DEFAULT_GATEWAY_ROUTES`. A non-failover route present in an existing saved route table SHALL NOT replace the default route.

#### Scenario: Route table loads with an old saved default route
- **WHEN** a saved route file holds an old non-failover route
- **THEN** the router initializes with the current default route for that virtual model

#### Scenario: Route table loads with a saved failover route
- **WHEN** a saved route file holds a route with a `failover:*` backend type
- **THEN** the router initializes with the saved failover route for that virtual model

## MODIFIED Requirements

### Requirement: A failover reset restores the default routes
`devops ai gateway failover --reset` and the MCP tool `ai_gateway_failover` with `reset` SHALL write the default route of every virtual model to the route table, clear the circuit breaker, and name the virtual models that were in failover. A reset SHALL write the route table also when `--simulate` is given. The command SHALL refuse a reset with a virtual model, and a call with neither a virtual model nor `--reset`, as a usage error.

#### Scenario: A reset after a failover
- **WHEN** a route table holds a route that is not a default route, `devops-reasoning` fails over, and then a reset runs
- **THEN** the reset reports `restored_routes` `["devops-reasoning"]` and no tripped circuit breaker, and the route file holds no failover routes and no tripped circuit breaker

#### Scenario: The MCP tool resets
- **WHEN** `devops-chat` fails over, and then the MCP tool `ai_gateway_failover` runs with `reset` and its default `simulate`
- **THEN** the route file holds no failover routes and no tripped circuit breaker

#### Scenario: A reset with a virtual model
- **WHEN** `devops ai gateway failover devops-chat --reset` runs, or `devops ai gateway failover` runs with no virtual model and no `--reset`
- **THEN** the command exits 2
