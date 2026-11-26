## ADDED Requirements

### Requirement: The bridge resolves typesafe/jev-1.14 and auto to decision models
`resolve_pydantic_ai_model` SHALL resolve `typesafe/jev-1.14` to `SystemOneModel` and `"auto"` to a `FallbackModel` of a `DecisionModel`. `SystemOneModel` SHALL post to `systemone` under `ai.gateway_url`, which the gateway of the environment tree serves as a pass-through.

#### Scenario: The model bridge is inspected
- **WHEN** the model that the bridge builds for `typesafe/jev-1.14` posts one request, and `resolve_pydantic_ai_model` resolves `typesafe/jev-1.14` and `auto`
- **THEN** the path of the request ends in `/systemone` under `ai.gateway_url`
- **AND** `resolve_pydantic_ai_model` returns a `SystemOneModel` for `typesafe/jev-1.14` and a `FallbackModel` wrapping `DecisionModel` for `auto`

#### Scenario: The client reads the answer of OpenRouter
- **WHEN** the answer holds `id`, `provider` and `usage.cost` next to `model`, `answers` and `usage`
- **THEN** the client returns the answers and the usage without an error

## MODIFIED Requirements

### Requirement: The implement job runs on a hosted gateway group
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL set the model of `ai.tasks.implement` and the one tier of each step class of `roadmap.implement.ladder` to a hosted gateway group. The `context_window` of the task SHALL hold the default step budget with the turn reserve.

#### Scenario: The template is read
- **WHEN** the template is validated as settings
- **THEN** the model of the task `implement` and each tier of each step class are a group of `CONST_AI_GATEWAY_HOSTED_MODELS`, and the two step classes have a ladder

#### Scenario: Each step class has the one DeepSeek tier
- **WHEN** the template is validated as settings
- **THEN** the ladder of each step class holds the one tier `openrouter/deepseek/deepseek-v4.1-flash-1017`, and a comment above the ladder says that a Sonnet tier is a later trial

#### Scenario: The window fits
- **WHEN** the window of the task `implement` is compared with the step budget plus the turn reserve
- **THEN** the window is not below the step budget plus the turn reserve

### Requirement: The job tasks of the Service template name their windows
Each job task of `k8s/devops/configmap.example.yaml` except `intake` and `retitle` SHALL set `context_window` 256000. Comments in the template SHALL give the reason and the end condition of each departure. The template SHALL NOT name `claude-sonnet-5-5` for any chat slot.

#### Scenario: The window of each job
- **WHEN** the template is read
- **THEN** the `context_window` of each job task except `intake` and `retitle` is 256000, and the template has no entry `analysis`, `verification` or `triage`

#### Scenario: The comment of the trial is read
- **WHEN** the lines above the task `stage` in the template are read
- **THEN** they name #4369, the date 2026-11-10, 67 USD a week, #3874 and Sonnet as a later trial

### Requirement: Documented gateway key of the Service and Jobs
The `devops/roadmap-service-llm-key` bullet of the Cluster Secrets section of `k8s/README.md` SHALL state that only the roadmap Service Deployment reads `DEVOPS_CLI_AI_API_KEY` from Secret `roadmap-service-llm-key`, while the stage Job and the runner Jobs read `DEVOPS_CLI_AI_API_KEY` from Secret `devops-cli`, naming the owner decision of 2026-11-20 (`#2695`, comment `7045868447`).

#### Scenario: Stage and runner Job keys in README
- **WHEN** a reader inspects the `devops/roadmap-service-llm-key` bullet of `k8s/README.md`
- **THEN** the bullet states that both the stage Job and the runner Jobs read `DEVOPS_CLI_AI_API_KEY` from Secret `devops-cli`, Deployment `devops/roadmap-service` reads `DEVOPS_CLI_AI_API_KEY` from Secret `roadmap-service-llm-key`, the 2026-11-20 owner decision (`#2695`, comment `7045868447`) is named, and no claim says the stage Job uses its own virtual key

## REMOVED Requirements

### Requirement: The LLM gateway serves typesafe/jev-1.14 and the bridge resolves System One and auto models
**Reason**: The gateway config that serves the pass-through route is in the environment repository (#7290).
**Migration**: See `The bridge resolves typesafe/jev-1.14 and auto to decision models`.
