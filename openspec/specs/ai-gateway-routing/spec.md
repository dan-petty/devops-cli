# ai-gateway-routing Specification

## Purpose
What devops-cli does with the LLM gateway: the route status and the failover of `devops ai gateway`, the render of the Ollama tiers and of the gateway routes into the environment tree, and what a call of the CLI to the gateway sends and how long it waits. The gateway config itself is in the environment tree of the cluster.

## Requirements

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

### Requirement: A saved route table keeps only failover state
The saved route table in `<data dir>/agent/gateway_state.json` SHALL keep only routes whose `backend_type` begins with `failover:`. When loading the route table, every non-failover route SHALL be taken from `DEFAULT_GATEWAY_ROUTES`. A non-failover route present in an existing saved route table SHALL NOT replace the default route.

#### Scenario: Route table loads with an old saved default route
- **WHEN** a saved route file holds an old non-failover route
- **THEN** the router initializes with the current default route for that virtual model

#### Scenario: Route table loads with a saved failover route
- **WHEN** a saved route file holds a route with a `failover:*` backend type
- **THEN** the router initializes with the saved failover route for that virtual model

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

### Requirement: An embedding-only tier serves embedding models first
A tier at or below `embedding_only` SHALL keep one model loaded, SHALL set `LLAMA_ARG_THREADS` to 1, SHALL have the speed tier `embed` and a name with `embed`, and each of its gateway deployments SHALL have order 1. The render SHALL fail and name each group when a generation deployment names such a tier.

#### Scenario: An embedding-only tier
- **WHEN** a tier is rendered at or below `embedding_only`
- **THEN** `OLLAMA_MAX_LOADED_MODELS` is 1, and `LLAMA_ARG_THREADS` is 1, and `OLLAMA_CONTEXT_LENGTH` is the largest RAG chunk, and each embedding deployment has order 1

#### Scenario: A chat tier keeps its CPU threads
- **WHEN** only `per_gpu` includes a tier
- **THEN** the tier does not set `LLAMA_ARG_THREADS`

#### Scenario: A chat route on an embedding-only tier
- **WHEN** a generation deployment names an embedding-only tier
- **THEN** the render fails, names the group and writes no file

### Requirement: A per-GPU tier runs one instance for each GPU
A tier at or below `per_gpu` SHALL render one DaemonSet, one Service and one gateway deployment for each GPU that its template names. Each DaemonSet SHALL claim one `nvidia.com/gpu`, SHALL set `OLLAMA_NOPRUNE`, and SHALL NOT set `OLLAMA_SCHED_SPREAD`. A later instance SHALL require a node with that many GPUs. The name and the VRAM labels of each SHALL give the VRAM of one GPU.

#### Scenario: Two GPUs at both thresholds
- **WHEN** the template of a 48 GiB tier with two GPUs is rendered at both thresholds
- **THEN** the output has `ollama-24gib-embed-gpu0` and `ollama-24gib-embed-gpu1`, and the Service of each selects only its instance

#### Scenario: The second instance
- **WHEN** the second instance is rendered
- **THEN** its node affinity requires an `nvidia.com/gpu.count` of 2 or more, and the first instance has no such requirement

#### Scenario: Each threshold acts alone
- **WHEN** only `per_gpu` includes a tier
- **THEN** each instance keeps the chat settings of the template, and none has an embedding deployment

### Requirement: A threshold with no tier to follow it is refused
The render SHALL fail for a threshold newer than the newest architecture of the tier templates.

#### Scenario: A newer threshold
- **WHEN** a threshold is `volta` and the newest architecture of the templates is `pascal`
- **THEN** the render fails and names `volta`

### Requirement: A request to a Claude group carries an output cap
The CLI SHALL set `max_tokens` on every request to a Claude group of the gateway, to a value above the Anthropic default of 4096 output tokens, so that the reply of a stage plan is not cut. A request to a model that is not a Claude group SHALL set no `max_tokens`, and keeps the limit of its gateway entry.

#### Scenario: A request to a Claude group
- **WHEN** an agent with a tool output sends a request to `claude-sonnet-5-5` through the gateway
- **THEN** the request body holds an output token limit above 4096

#### Scenario: A request to another model
- **WHEN** an agent sends a request to `devops-chat` or to `deepseek-v4.1-flash-1017` through the gateway
- **THEN** the request body holds no output token limit

### Requirement: A request to a Claude group forbids parallel tool calls
The CLI SHALL set `parallel_tool_calls` to false on every request with tools to a Claude group of the gateway, so that the model makes one tool call per reply and the gateway joins no arguments of several calls into one JSON text. A request to a model that is not a Claude group SHALL set no `parallel_tool_calls`.

#### Scenario: A request to a Claude group
- **WHEN** an agent with a tool output sends a request to `claude-sonnet-5-5` through the gateway
- **THEN** the request body holds `parallel_tool_calls` with the value false

#### Scenario: A request to another model
- **WHEN** an agent sends a request to `devops-chat` or to `deepseek-v4.1-flash-1017` through the gateway
- **THEN** the request body holds no `parallel_tool_calls`

### Requirement: A gateway attempt ends before the deadline of the call
The default of `ai.request_timeout_seconds` SHALL be less than `CONST_ROADMAP_STAGE_JOB_MARGIN_SECONDS` and the `activeDeadlineSeconds` of `k8s/devops/cronjob-runner.yaml`. The gateway config of the environment tree sets the router timeout, which has to be less than the call deadlines.

#### Scenario: The timeouts nest
- **WHEN** a person runs `kubectl -n llm get configmap -l app.kubernetes.io/name=llm-gateway -o yaml` and `kubectl -n devops get cronjob devops-cli-runner -o yaml` on the cluster
- **THEN** the router timeout and each deployment timeout of the gateway config are less than each default call deadline, and the default of `ai.request_timeout_seconds` is less than the stage margin and the `activeDeadlineSeconds` of the runner CronJob

### Requirement: A direct gateway call is sent again only after a failed connect
`LLMClient` with provider `gateway` SHALL send a call again only when its connect failed or it got no connection from the pool, at most `ai.max_retries` + 1 times. It SHALL not send a call again after a status of the gateway. A client of another provider SHALL keep the retries of its transport.

#### Scenario: The gateway answers 503
- **WHEN** `ai.max_retries` is 3 and the gateway answers a call with status 503
- **THEN** the gateway got 1 call, and the client raises `AIClientError` with status 503

#### Scenario: Each connect fails
- **WHEN** `ai.max_retries` is 3 and each connect to the gateway fails
- **THEN** the transport saw 4 calls, and the client raises `AIClientError`

### Requirement: A rendered tier keeps the annotations of its template that control no render
The render SHALL drop the annotations `llm.devops.io/gpu-count` and `llm.devops.io/embedding-model` of a tier template, which control the render, and SHALL keep each other annotation of the template on each tier that it writes, such as the reason of a kube-linter exception.

#### Scenario: A template with a kube-linter exception
- **WHEN** a tier template holds the two control annotations and the annotation `ignore-check.kube-linter.io/run-as-non-root`, and the render writes it at both thresholds or above both
- **THEN** each tier that the render writes holds only the annotation `ignore-check.kube-linter.io/run-as-non-root`

### Requirement: Live gateway status queries model info and marks static fallbacks not checked
When `GET /model/info` answers, `devops ai gateway status` SHALL authenticate with the configured AI API key (`get_ai_api_key`) and render each served group and deployment while preserving recorded failover routes in `gateway_state.json`. When `GET /model/info` does not answer, `devops ai gateway status` SHALL fall back to `DEFAULT_GATEWAY_ROUTES` and mark each fallback row as `not checked`.

#### Scenario: Live gateway answers model info with active failover
- **WHEN** `devops ai gateway status` runs with an AI API key configured, a recorded failover, and a gateway returning two `devops-chat` deployments and `qwen3-embedding:0.6b` from `GET /model/info`
- **THEN** `GET /model/info` carries the configured bearer key, both `devops-chat` deployments and `qwen3-embedding:0.6b` render (`checked: true`), and the failover record stays active

#### Scenario: Model info is unreachable
- **WHEN** `devops ai gateway status` runs and `GET /model/info` fails or times out
- **THEN** `DEFAULT_GATEWAY_ROUTES` render with `not checked` (`checked: false`)

### Requirement: The render follows the thresholds of the environment tree
`devops ai gateway render` SHALL read `embedding_only` and `per_gpu` from `llm/profiles/gpu-thresholds.yaml` of the environment tree, each a value of `nvidia.com/gpu.architecture`. A tier template SHALL be at or below a threshold when the newest architecture that it accepts is that architecture or an older one. A tier newer than both thresholds SHALL run as its template says, with no embedding deployment.

#### Scenario: A tier newer than both thresholds
- **WHEN** a tier that accepts `pascal` is rendered with the thresholds `maxwell` and `kepler`
- **THEN** its DaemonSet equals its template, and it has no embedding deployment

#### Scenario: An unknown architecture
- **WHEN** a threshold names an architecture that the label does not have
- **THEN** the load fails and names the value

### Requirement: A render writes only the rendered regions
`devops ai gateway render` SHALL write only the regions between the `rendered` lines of the profiles, the services and the gateway config of the tree. Without `--apply`, it SHALL show the diff and write no file.

#### Scenario: A second render
- **WHEN** the output of a render is rendered again with the same inputs
- **THEN** the output does not change

#### Scenario: A lower threshold
- **WHEN** an output of a higher threshold is rendered with a lower one
- **THEN** the output equals a render of the lower threshold from empty regions
