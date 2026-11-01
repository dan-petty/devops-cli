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

### Requirement: The gateway routes qwen3.8:27b and devops-chat only to 48gib and 64gib tiers
The gateway configuration SHALL NOT deploy `qwen3.8:27b` or `devops-chat` to the 16gib serving tier. Deployments for `qwen3.8:27b` and `devops-chat` SHALL only target serving tiers with at least 48 GiB total VRAM.

#### Scenario: Gateway deployments for qwen3.8:27b and devops-chat
- **WHEN** the gateway configuration is loaded
- **THEN** every deployment for `qwen3.8:27b` and `devops-chat` targets `ollama-48gib-fast` or `ollama-64gib-standard`, and no deployment targets `ollama-16gib-fast`

### Requirement: The MCP gateway tools publish no URL
The MCP tools `ai_gateway_status`, `ai_gateway_routes` and `ai_gateway_probe_backend` SHALL publish no gateway URL and no backend URL. `ai_gateway_status` and `ai_gateway_routes` SHALL publish only `provider`. `ai_gateway_probe_backend` SHALL publish only `backend`. A call that gives a URL SHALL fail and send no request.

#### Scenario: The tool schemas
- **WHEN** an MCP client lists the tools
- **THEN** `ai_gateway_status` and `ai_gateway_routes` publish the parameter `provider` and no other, and `ai_gateway_probe_backend` publishes the parameter `backend` and no other

#### Scenario: A call that gives a backend URL
- **WHEN** a client calls `ai_gateway_probe_backend` with `backend_url` set to a loopback URL
- **THEN** the call fails and the socket gets no dial to that host

#### Scenario: A call that gives a gateway URL
- **WHEN** a client calls `ai_gateway_routes` or `ai_gateway_status` with `gateway_url` set to a public URL, and the AI API key is set
- **THEN** the call fails, the socket gets no dial to that host, and the AI API key is not on the wire

### Requirement: The MCP gateway tools dial the configured gateway at the configured level
Each of the three MCP gateway tools SHALL query the configured gateway or backend. It SHALL dial loopback and public addresses. It SHALL dial private addresses only when `ai.allow_private_network` is true.

#### Scenario: The configured service at the configured level
- **WHEN** a tool runs, and the host of `ai.gateway_url` or `ai.ollama_urls` answers `127.0.0.1` or `192.0.2.10`
- **THEN** the tool dials `127.0.0.1` whatever `ai.allow_private_network` says, and dials `192.0.2.10` only when `ai.allow_private_network` is true

#### Scenario: The key goes to the configured gateway
- **WHEN** `ai_gateway_routes` runs with the AI API key set
- **THEN** the request to the host of `ai.gateway_url` carries the key

### Requirement: The AI API key goes only to the configured gateway
The model query of a gateway SHALL send the AI API key only to a configured gateway. A configured gateway has the scheme, host and port of `ai.gateway_url` or `ai.portkey_url`. `devops ai gateway routes` and `devops ai gateway tune` SHALL get this rule. A URL of another origin SHALL get no key, and so SHALL any URL when no gateway is configured. When such a gateway answers HTTP 401 or 403 and a key is set, the error SHALL say that the gateway got no key. It SHALL NOT ask for a key.

#### Scenario: The configured origin
- **WHEN** `--gateway-url` has the origin of `ai.gateway_url`, with the same path, another path or another spelling of the host
- **THEN** the request carries the AI API key

#### Scenario: Another origin
- **WHEN** `--gateway-url` has another host, another port, a port that starts with the configured port, or another scheme, or no gateway is configured
- **THEN** the request carries no AI API key

#### Scenario: Another gateway refuses the request
- **WHEN** a gateway of another origin answers HTTP 401 and the AI API key is set
- **THEN** the error says that this gateway got no key, because the key goes only to the configured gateway
- **AND** the error holds the host and port of that gateway and no URL

### Requirement: Gateway routes devops-triage to the standard tier
The LiteLLM gateway configuration SHALL define a `devops-triage` model group with one deployment: `ollama_chat/qwen3.8:27b` on the 64 GiB standard tier.

#### Scenario: The devops-triage route
- **WHEN** the gateway configuration is loaded
- **THEN** `devops-triage` routes to `ollama_chat/qwen3.8:27b` on `http://ollama-64gib-standard.llm.svc.cluster.local:11434`

### Requirement: Gateway fallbacks include triage and background targets
The gateway router settings fallbacks SHALL include `devops-triage: [qwen3.8:27b]` and `devops-background: [qwen3.8:27b]`.

#### Scenario: Fallback routes
- **WHEN** `devops-triage` or `devops-background` fails all retries
- **THEN** the request falls back to `qwen3.8:27b`

### Requirement: Each chat deployment of the gateway declares the window of its tier
Each `ollama_chat` deployment of the gateway config SHALL set `max_input_tokens` in its top-level `model_info`, equal to the `OLLAMA_CONTEXT_LENGTH` of its tier. No deployment SHALL set `model_info` inside `litellm_params`.

#### Scenario: The windows of the chat deployments
- **WHEN** the gateway config is loaded
- **THEN** each `ollama_chat` deployment has a `model_info.max_input_tokens` equal to the context length of the tier that its `api_base` names

#### Scenario: A model_info inside litellm_params
- **WHEN** a deployment of the gateway config sets `model_info` inside `litellm_params`
- **THEN** the check names that deployment

### Requirement: The gateway has no context-window fallback
The router settings of the gateway config SHALL NOT set `context_window_fallbacks`. No deployment has a window above the 262144 tokens of `ollama-48gib-fast`.

#### Scenario: The router settings
- **WHEN** the gateway config is loaded
- **THEN** `router_settings` has no `context_window_fallbacks`, and `enable_pre_call_checks` is true

### Requirement: Every Ollama tier sets one KV cache type
Each DaemonSet in `k8s/llm/profiles/ollama-profiles.yaml` SHALL set `OLLAMA_KV_CACHE_TYPE` to `q8_0`. The KV cache type changes the vectors of an embedding model, so every tier that the gateway sends embeddings to SHALL make the same vector for the same input.

#### Scenario: The KV cache type of the nine tiers
- **WHEN** a check reads the `OLLAMA_KV_CACHE_TYPE` value of every container of every DaemonSet in `k8s/llm/profiles/ollama-profiles.yaml`
- **THEN** it finds nine values, and each of them is `q8_0`
