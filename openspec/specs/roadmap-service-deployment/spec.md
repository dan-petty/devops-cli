# roadmap-service-deployment Specification

## Purpose
How the roadmap Service and the cluster Jobs run in namespace `devops`: the replica count of `deployment/roadmap-service`, and the model retry count of ConfigMap `devops-cli-config`, which both read.

## Requirements

### Requirement: The Service runs as one pod
`deployment/roadmap-service` SHALL set `replicas: 1` and the `Recreate` strategy, so one pod of the Service runs at a time.

#### Scenario: The manifest is read
- **WHEN** `k8s/devops/roadmap-service/deployment.yaml` is read
- **THEN** its `spec.replicas` is 1 and its `spec.strategy.type` is `Recreate`

### Requirement: A model call in the cluster is sent at most two times
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL set `ai.max_retries` to 1, and the ConfigMap that a deploy renders from it SHALL keep that value.

#### Scenario: A deploy renders the ConfigMap from the repository's template
- **WHEN** the active config sets `service.repos` and the App's settings, and the ConfigMap is rendered from `k8s/devops/configmap.example.yaml`
- **THEN** the rendered config validates as settings with `ai.max_retries` 1

### Requirement: The Service image runs the pinned OpenSpec
The Service image of `Dockerfile` SHALL carry the `node` binary of a digest-pinned `node` image whose major version is the one in `.node-version`, and the OpenSpec that `devops install-tools --tool openspec` installs from the lockfile of `src/devops_cli/tools_lock/openspec`. The directory of its `openspec` link SHALL be on the `PATH` of the service stage. The stage SHALL set `OPENSPEC_TELEMETRY=0`, `OPENSPEC_NO_UPDATE_CHECK=1` and `DO_NOT_TRACK=1`.

#### Scenario: OpenSpec comes from the lockfile
- **WHEN** the builder stage, the `service-deps` stage and the service stage of `Dockerfile` are read
- **THEN** the builder stage runs `devops install-tools --tool openspec` with a `--target-dir`, `service-deps` copies the tool directory from the builder to the same path, the service stage builds on `service-deps`, and that `--target-dir` is on the `PATH` of the service stage

#### Scenario: The telemetry is off
- **WHEN** the environment of the service stage is read
- **THEN** it sets `OPENSPEC_TELEMETRY` to 0, `OPENSPEC_NO_UPDATE_CHECK` to 1 and `DO_NOT_TRACK` to 1

#### Scenario: The Node runtime is the one of CI
- **WHEN** the `node` stage of `Dockerfile` is read
- **THEN** its image is pinned by digest and its major version equals the content of `.node-version`, and the builder, `runner-deps` and `service-deps` stages copy the `node` binary from it

### Requirement: A deploy keeps the hourly request budget
The ConfigMap that a deploy renders SHALL hold `service.github_requests_per_hour` when the active settings set it, and SHALL hold no such key when they do not.

#### Scenario: The active settings set the budget
- **WHEN** the active settings set `service.github_requests_per_hour` to 2000 and the ConfigMap is rendered
- **THEN** the `service` section of the rendered config holds `github_requests_per_hour: 2000`

#### Scenario: The active settings keep the default
- **WHEN** the active settings set no `service.github_requests_per_hour` and the ConfigMap is rendered
- **THEN** the `service` section of the rendered config holds no `github_requests_per_hour`

### Requirement: The implement job runs on a hosted gateway group
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL set the model of `ai.tasks.implement` and the one tier of each step class of `roadmap.implement.ladder` to a hosted group that `k8s/llm/gateway/config.yaml` serves. The `context_window` of the task SHALL NOT be above the `max_input_tokens` of that group, and SHALL hold the default step budget with the turn reserve.

#### Scenario: The template is read
- **WHEN** the template is validated as settings and the gateway config is read
- **THEN** the model of the task `implement` and each tier of each step class are a hosted group in the `model_list` of the gateway config, and the two step classes have a ladder

#### Scenario: Each step class has the one DeepSeek tier
- **WHEN** the template is validated as settings
- **THEN** the ladder of each step class holds the one tier `openrouter/deepseek/deepseek-v4.1-flash-1017`, and a comment above the ladder says that a Sonnet tier is a later trial

#### Scenario: The window fits
- **WHEN** the window of the task `implement` is compared with the window of its group and with the step budget plus the turn reserve
- **THEN** the window is not above the window of the group and is not below the step budget plus the turn reserve

### Requirement: The stage task has its own entry
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL list `stage` as its own key of `ai.tasks` with the model `openrouter/deepseek/deepseek-v4.1-flash-1017` and `context_window` 256000.

#### Scenario: The stage task has its own entry
- **WHEN** the `ai.tasks` section of the template is read
- **THEN** `stage` is an explicit key with the model `openrouter/deepseek/deepseek-v4.1-flash-1017` and `context_window` 256000

### Requirement: The Service container has memory for the observed growth
Container `service` of `deployment/roadmap-service` SHALL request `768Mi` of memory and limit it to `3Gi`, and SHALL keep the CPU request `100m` with a CPU limit of `2`. The memory limit SHALL be at least 460 MiB plus 10 hours of growth at 150 MiB each hour, so the alert `RoadmapServiceMemoryNearLimit` fires before a kill. The comment above `resources` SHALL say that the memory raise is a stopgap and SHALL link #4116 and #4125.

#### Scenario: The manifest is read
- **WHEN** `k8s/devops/roadmap-service/deployment.yaml` is read
- **THEN** the resources of container `service` are a memory request of `768Mi`, a memory limit of `3Gi`, a CPU request of `100m` and a CPU limit of `2`

#### Scenario: The limit is cut
- **WHEN** the memory limit of container `service` is below 460 MiB plus 10 times 150 MiB
- **THEN** the test fails and its message names #4116

### Requirement: The ConfigMap template names the reference models
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL set `ai.reference_model` to `qwen3.8:27b` and `ai.reference_embedding_model` to `qwen/qwen3-embedding-8b`, so the spend reports of the Service value local tokens at the hosted prices of these two models. The comment above the keys SHALL give the owner decision, its date 2026-11-09, the three prices, and the file `pricing_overrides.json` whose price wins over the price in the template.

#### Scenario: The rendered template is read
- **WHEN** the ConfigMap is rendered from the repository's template and validated as settings
- **THEN** `ai.reference_model` is `qwen3.8:27b` and `ai.reference_embedding_model` is `qwen/qwen3-embedding-8b`

#### Scenario: The comment is read
- **WHEN** the comment lines above `reference_model` in the template are read
- **THEN** they name the date 2026-11-09, the prices 0.035, 1.50 and 0.01, and the file `pricing_overrides.json`

### Requirement: The ConfigMap template holds the prices of the reference models
The ConfigMap template SHALL set `ai.price_overrides` for both reference models, so a new data volume needs no hand step: 0.035 USD input and 1.50 USD output per million tokens for `qwen3.8:27b`, and 0.01 USD input and 0 USD output for `qwen/qwen3-embedding-8b`.

#### Scenario: The rendered template is read for prices
- **WHEN** the ConfigMap is rendered from the repository's template and validated as settings
- **THEN** `ai.price_overrides` holds 0.035 and 1.50 for `qwen3.8:27b` and 0.01 and 0 for `qwen/qwen3-embedding-8b`

### Requirement: The LLM gateway serves typesafe/jev-1.14 and the bridge resolves System One and auto models
`k8s/llm/gateway/config.yaml` SHALL serve `typesafe/jev-1.14` as the authenticated pass-through `POST /v1/systemone` to the System One endpoint of OpenRouter, with the OpenRouter key from the environment of the gateway, and SHALL NOT list it in `model_list`. The path of `SystemOneModel` under `ai.gateway_url` SHALL be that path. `resolve_pydantic_ai_model` SHALL resolve `typesafe/jev-1.14` to `SystemOneModel` and `"auto"` to a `FallbackModel` of a `DecisionModel`.

#### Scenario: The gateway config and model bridge are inspected
- **WHEN** the model that the bridge builds for `typesafe/jev-1.14` posts one request, `k8s/llm/gateway/config.yaml` is loaded, and `resolve_pydantic_ai_model` resolves `typesafe/jev-1.14` and `auto`
- **THEN** the path of the request is the `path` of an entry of `general_settings.pass_through_endpoints` that targets the System One endpoint of OpenRouter with `auth: true`
- **AND** `model_list` holds no entry named `typesafe/jev-1.14`
- **AND** `resolve_pydantic_ai_model` returns a `SystemOneModel` for `typesafe/jev-1.14` and a `FallbackModel` wrapping `DecisionModel` for `auto`

#### Scenario: The client reads the answer of OpenRouter
- **WHEN** the answer holds `id`, `provider` and `usage.cost` next to `model`, `answers` and `usage`
- **THEN** the client returns the answers and the usage without an error

### Requirement: The devops stack includes the role-scoped MCP server and disables workload telemetry banners
`k8s/devops/kustomization.yaml` and `MANIFESTS_BY_STACK["devops"]` SHALL include `k8s/devops/mcp-server/` (`deployment.yaml`, `service.yaml`, `networkpolicy.yaml`, `networkpolicy-client.yaml`), and `mcp-server`, `cronjob-runner`, and `roadmap-service` SHALL set `DO_NOT_TRACK=1`, `OPENSPEC_TELEMETRY=0`, `OPENSPEC_NO_UPDATE_CHECK=1`, and `PYDANTIC_AI_NO_BANNER=1`.

#### Scenario: The devops kustomization and workload manifests are read
- **WHEN** `k8s/devops/` manifests are validated
- **THEN** `mcp-server` is listed in `k8s/devops/kustomization.yaml` and `MANIFESTS_BY_STACK["devops"]`
- **AND** `mcp-server`, `cronjob-runner`, and `roadmap-service` set the four telemetry and banner opt-out variables

### Requirement: The Service reads its own gateway key
The roadmap Service Deployment SHALL read `DEVOPS_CLI_AI_API_KEY` from key `api-key` of Secret `roadmap-service-llm-key`. Its pod template SHALL NOT hold an `envFrom` entry for Secret `devops-cli`, and each other variable of that Secret SHALL have an explicit `secretKeyRef`, with `optional: true` on the four optional keys.

#### Scenario: The rendered Deployment
- **WHEN** `kustomize build k8s/devops/roadmap-service/` renders the Deployment
- **THEN** `DEVOPS_CLI_AI_API_KEY` has one `secretKeyRef` to `roadmap-service-llm-key` with key `api-key`, the pod template has no `envFrom`, and each other variable names its key of `devops-cli`

### Requirement: The example ConfigMap holds the runner memory limit
The example ConfigMap SHALL set `roadmap.implement.max_memory_limit` to 16Gi, with a comment that names the two out-of-memory kills of 2026-11-12 and 2026-11-13, and the render of the ConfigMap SHALL keep that value for every repository.

#### Scenario: The rendered example holds the limit
- **WHEN** a test renders the example ConfigMap for one repository with the GitHub App settings
- **THEN** the rendered config holds 16Gi as the runner memory limit and the service.repos of that repository

#### Scenario: The comment names the two kills
- **WHEN** a test reads the comment above the setting in the example ConfigMap
- **THEN** the comment names 2026-11-12, 2026-11-13, #5484 and #3727

### Requirement: The roadmap key bootstrap command provisions the virtual key
`devops k8s bootstrap-roadmap-key` SHALL read the gateway master key from Secret `llm-gateway-secrets` in namespace `llm`, call `POST /key/generate` on the LLM gateway, store the generated key in the OS keyring as `roadmap_service.llm_key`, and apply Secret `roadmap-service-llm-key` in namespace `devops` with key `api-key`.

#### Scenario: The command bootstraps the roadmap service key
- **WHEN** `devops k8s bootstrap-roadmap-key` runs without `--dry-run`
- **THEN** it generates a virtual key on the LiteLLM gateway, saves it to the OS keyring, and pushes Secret `roadmap-service-llm-key` to namespace `devops`

#### Scenario: Dry run makes no external modifications
- **WHEN** `devops k8s bootstrap-roadmap-key --dry-run` runs
- **THEN** it lists the planned generation, keyring storage, and Secret push without calling the gateway, writing to the keyring, or modifying the cluster

### Requirement: The ConfigMap template holds the doubled stage limits
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL set each attempt limit of `roadmap.stage` to two times its code default.

#### Scenario: The stage limits are read
- **WHEN** the template is validated as settings
- **THEN** `verify_repair_rounds`, `verify_repair_rounds_ceiling`, `gate_returns`, `gate_return_extensions`, `plan_defect_limit`, `max_requests` and `max_tool_calls` of `roadmap.stage` are each two times their `DEFAULT_` constant

### Requirement: The ConfigMap template holds the doubled implement limits
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL set each attempt limit of `roadmap.implement` to two times its code default, the two token budgets to four times, and the item time to the ceiling of the Job deadline.

#### Scenario: The implement limits are read
- **WHEN** the template is validated as settings
- **THEN** `repair_rounds`, `command_timeout_seconds`, `request_timeout_seconds`, `monitor_timeout_seconds`, `step_time_limit_seconds`, `deadline_stall_seconds`, `deadline_extension_seconds`, `digest_clears_per_class`, `digest_clears_per_item`, `continuations_per_item`, `max_requests`, `max_tool_calls`, `tool_retries`, `max_refusals`, `max_consecutive_refusals` and `model_resends` of `roadmap.implement` are each two times their `DEFAULT_` constant

#### Scenario: The item time of implement is read
- **WHEN** the template is validated as settings
- **THEN** `roadmap.implement.item_time_limit_seconds` equals `DEFAULT_ROADMAP_IMPLEMENT_DEADLINE_CEILING_SECONDS`

#### Scenario: The token budgets of implement are read
- **WHEN** the template is validated as settings
- **THEN** `step_token_budget` and `item_token_budget` of `roadmap.implement` are each four times their `DEFAULT_` constant

### Requirement: The ConfigMap template holds the doubled fix-plan limits
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL set `time_budget_seconds`, `head_attempts` and `revisions` of `roadmap.fix_plan` to two times their code defaults.

#### Scenario: The fix-plan limits are read
- **WHEN** the template is validated as settings
- **THEN** `time_budget_seconds`, `head_attempts` and `revisions` of `roadmap.fix_plan` are each two times their `DEFAULT_` constant

### Requirement: Each roadmap job of the Service template names its own model
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL name `openrouter/deepseek/deepseek-v4.1-flash-1017` for `ai.model`, for the task `chat` and for each job task except `intake` and `retitle`, and `local/qwen3.8:27b` for these two tasks. It SHALL name `local/qwen3-embedding:0.6b` for the task `embedding`, and SHALL set no entry for the tasks `analysis`, `verification` and `triage`.

#### Scenario: The rendered template is read
- **WHEN** the ConfigMap is rendered from the repository's template and validated as settings
- **THEN** `ai.model` and the model of each task except `embedding`, `intake` and `retitle` are `openrouter/deepseek/deepseek-v4.1-flash-1017`, the model of `intake` and `retitle` is `local/qwen3.8:27b`, and the model of the task `embedding` is `local/qwen3-embedding:0.6b`

### Requirement: The job tasks of the Service template name their windows
Each job task of `k8s/devops/configmap.example.yaml` except `intake` and `retitle` SHALL set `context_window` 256000. Comments in the template SHALL give the reason and the end condition of each departure. The template SHALL NOT name `claude-sonnet-5-5` for any chat slot.

#### Scenario: The window of each job
- **WHEN** the template is read
- **THEN** the `context_window` of each job task except `intake` and `retitle` is 256000, the template has no entry `analysis`, `verification` or `triage`, and the window of `stage` is not above the `max_input_tokens` of the gateway group of the model of `stage` in `k8s/llm/gateway/config.yaml`

#### Scenario: The comment of the trial is read
- **WHEN** the lines above the task `stage` in the template are read
- **THEN** they name #4369, the date 2026-11-10, 67 USD a week, #3874 and Sonnet as a later trial
