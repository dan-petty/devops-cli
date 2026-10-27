# ai-gateway-routing Specification

## Purpose
The routes of `devops ai gateway`: the model and the Ollama Service that each virtual model of the gateway uses, the route that a failover of a virtual model records, and the default models that the CLI and Open WebUI name for the gateway and its tiers.

## Requirements

### Requirement: Every gateway route names a model that its tier serves
Each default route of `devops ai gateway`, and the route that a failover of each virtual model records, SHALL name a model that a deployment of the gateway config sends to a serving tier that the route's Ollama Service selects.

#### Scenario: The default routes
- **WHEN** `devops ai gateway routes` lists a new route table
- **THEN** each route names a model that the gateway config sends to a serving tier of the route's Service

#### Scenario: The route that a failover records
- **WHEN** each virtual model fails over on a new route table
- **THEN** the route that the failover records names a model that the gateway config sends to a serving tier of the route's Service

### Requirement: A failover to direct Ollama keeps the model of the default route
When a virtual model fails over to `direct-ollama`, the route that the failover records SHALL name the target model of the virtual model's default route, on the default Ollama Service, with the backend type `failover:ollama`.

#### Scenario: devops-chat fails over
- **WHEN** `devops-chat` fails over on a new route table
- **THEN** its route names `qwen3.8:27b` on the default Ollama Service, with the backend type `failover:ollama`

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
- **THEN** the reset reports `restored_routes` `["devops-reasoning"]` and no tripped circuit breaker, and the route file holds no failover routes and no tripped circuit breaker

#### Scenario: The MCP tool resets
- **WHEN** `devops-chat` fails over, and then the MCP tool `ai_gateway_failover` runs with `reset` and its default `simulate`
- **THEN** the route file holds no failover routes and no tripped circuit breaker

#### Scenario: A reset with a virtual model
- **WHEN** `devops ai gateway failover devops-chat --reset` runs, or `devops ai gateway failover` runs with no virtual model and no `--reset`
- **THEN** the command exits 2

### Requirement: The default fallback model is a model that the default Ollama tier serves
The default fallback model of `devops ai failover` and `devops ai chaos-model`, and the default model of the harness model slots, SHALL be a model that a deployment of the gateway config sends to a serving tier that the default Ollama Service selects.

#### Scenario: The CLI default and the harness slots
- **WHEN** `devops ai failover` and `devops ai chaos-model` run with no fallback model, and a harness model slot or sub-agent slot is made with no model
- **THEN** each names a model that the gateway config sends to a serving tier of the default Ollama Service

### Requirement: Each Open WebUI default model is a group that the gateway serves
Each model that the `DEFAULT_MODELS` of the Open WebUI values names SHALL be a model group of the gateway config with a deployment on a serving tier. The Open WebUI values SHALL NOT set `MODEL_FILTER_LIST`, which Open WebUI does not read.

#### Scenario: The Open WebUI values
- **WHEN** the Open WebUI values are read
- **THEN** each model of `DEFAULT_MODELS` is a gateway group with a deployment on a serving tier, and the values set no `MODEL_FILTER_LIST`

#### Scenario: A model that the gateway does not serve
- **WHEN** the check reads `qwen2.5-coder:7b`, `devops-flagship` or an Ollama model name that is no group
- **THEN** it names each of them, and it passes `devops-chat` and `qwen3-coder:30b`

### Requirement: Each default model of the CLI is a model that the default Ollama tier and the gateway serve
The default of `ai.model`, each model of `devops ai bundle-models`, and the model that a task benchmark runs when it gets no candidate SHALL be a model that a deployment of the gateway config sends to a serving tier that the default Ollama Service selects. Each SHALL also be a model group of the gateway config with a deployment on a serving tier.

#### Scenario: The defaults with no configuration
- **WHEN** the CLI runs with no `ai.model` set, `devops ai bundle-models` runs, and a task benchmark gets no candidate
- **THEN** each names a model that the gateway config sends to a serving tier of the default Ollama Service, and a gateway group with a deployment on a serving tier

#### Scenario: The benchmark with no candidate
- **WHEN** a task benchmark gets an empty list of candidates
- **THEN** it runs the configured `ai.model`

### Requirement: Each virtual model of the GPU matrix is a group that the gateway serves
The virtual model of each hardware profile and of each Service alias that `devops k8s gpu-matrix` shows SHALL be a model group of the gateway config with a deployment on a serving tier.

#### Scenario: The GPU matrix
- **WHEN** `devops k8s gpu-matrix` reads its profiles and Service aliases
- **THEN** each virtual model is a gateway group with a deployment on a serving tier, and a 70B profile names `deepseek-r1:70b`

### Requirement: The gateway routes embeddings with simple-shuffle across order 1 tiers
The gateway configuration SHALL configure a routing group for the `qwen3-embedding:0.6b` model with `routing_strategy: simple-shuffle`, spreading sequential and parallel batches across all order 1 serving tiers.

#### Scenario: Gateway router settings
- **WHEN** the gateway configuration is loaded
- **THEN** `router_settings.routing_groups` contains a group for `qwen3-embedding:0.6b` with `simple-shuffle` routing strategy

### Requirement: A saved route table keeps only failover state
The saved route table in `<data dir>/agent/gateway_state.json` SHALL keep only routes whose `backend_type` begins with `failover:`. When loading the route table, every non-failover route SHALL be taken from `DEFAULT_GATEWAY_ROUTES`. A non-failover route present in an existing saved route table SHALL NOT replace the default route.

#### Scenario: Route table loads with an old saved default route
- **WHEN** a saved route file holds an old non-failover route
- **THEN** the router initializes with the current default route for that virtual model

#### Scenario: Route table loads with a saved failover route
- **WHEN** a saved route file holds a route with a `failover:*` backend type
- **THEN** the router initializes with the saved failover route for that virtual model
