# Proposal

## Why

Issue #3573: the owner wants a cheap hosted model for the whole Service, while the local models are slow.
The planning lane already runs on `deepseek-v4.1-flash-1017` through the slot `ai.tasks.analysis`. The implement job still runs on the local group `devops-coder`, because `ai.tasks.implement` and `roadmap.implement.ladder` keep their defaults.
This change sets the example ConfigMap so that the implement job, in every step class, runs on `deepseek-v4.1-flash-1017`, and holds that setting to the gateway config with a test.

## What Changes

- `k8s/devops/configmap.example.yaml` sets `ai.tasks.implement` to the model `deepseek-v4.1-flash-1017` with the `context_window` 256000, and sets `roadmap.implement.ladder` to that one group for `plan`, `edit`, `repair` and `review`.
- A test holds the model and the tiers of the example to a hosted group that `k8s/llm/gateway/config.yaml` serves, and holds the window to the window of that group and to a step with the turn reserve.
- `k8s/README.md`, `docs/roadmap/implement.md` and `SECURITY.md` state the new routing. The prompts of an implement step, which hold the code of every repository of the Service, now leave the cluster to OpenRouter and DeepSeek. The owner chose this. `claude-sonnet-5-5` serves no step.
- No code changes. The settings, their validators and the factory already accept a hosted tier.
- The change is observable (a manifest), so it carries a spec delta.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-service-deployment`: add the requirement for the implement model and ladder of the template.

## Impact

- The merge does not deploy. Argo CD does not apply ConfigMap `devops-cli-config`. A person runs `devops k8s deploy-stack --stack devops` from a checkout of `main`, which renders the ConfigMap from the template. The CronJob and the runner Jobs read it at each run. The Service reads it at its start, so a person also restarts `deployment/roadmap-service`.
- The live ConfigMap is older than the template on other keys too (for example `planned_limit`, `toolset`, `step_tokens`). The same deploy brings them.
- To roll back, revert the lines of the template and run the deploy again, or delete the keys `ai.tasks.implement` and `roadmap.implement` from the live ConfigMap.
- A step has one tier, so a failure that selects `change_tier` ends the step and the item stops. There is no stronger tier to move to.
- The change fits in one pull request.

## Feasibility

- The public OpenRouter API (`/api/v1/models` and `/api/v1/models/deepseek/deepseek-v4.1-flash-1017/endpoints`, read on 2026-11-05) lists `deepseek/deepseek-v4.1-flash-1017` with `context_length` 1,048,576, and with `tools`, `tool_choice`, `response_format` and `structured_outputs` in `supported_parameters`. The implement agent needs tools, so tool calling is confirmed.
- Of the 48 endpoints of the model, 21 have fp8 weights, which the gateway group requires (`quantizations: [fp8]`). They offer a window from 256,000 (one provider) to 1,048,576 tokens, and each lists `tools`. Two fp8 endpoints list no `structured_outputs`; the implement agent uses tools and no structured reply. The route `:floor` picks the cheapest endpoint, so the window that holds on every endpoint is 256,000. That is the `context_window` of the task.
- `roadmap.implement.ladder` takes a hosted group: the validator `_check_ladder` in `src/devops_cli/config/settings.py` accepts every name in `CONST_AI_GATEWAY_HOSTED_MODELS`, which holds `deepseek-v4.1-flash-1017`. `get_tier_model` in `src/devops_cli/ai/client/factory.py` sends a group tier to the configured gateway. `get_task_model("implement")` reads `ai.tasks.implement`. `Settings.model_validate` of the example gives the model, the window 256000 and four one-tier ladders.
- The Service and the runner Jobs read one ConfigMap: the Deployment and CronJob `devops-cli-runner` mount `devops-cli-config`, and the Job of a live run (checked read-only with `kubectl`) mounts it with `DEVOPS_CLI_CONFIG=/config/devops-cli.yaml`. The ConfigMap is not in the resources of the `devops` Application, so a merge does not apply it (`k8s/README.md`, Go-live check).
- The step refuses an input above the window minus the turn reserve. The default `roadmap.stage.step_tokens` is 64000 and the turn reserve is 40000, so a step needs 104000 tokens, under 256000. `step_tokens` stays at 64000.
- A live run on 2026-11-05 of `devops roadmap eval implement --model deepseek-v4.1-flash-1017 -F 2152-numeric-host-doubles` ended `done` with five properties passed and one skipped (no command to run). It made 42 model requests and 51 tool calls in 281 s, with 2,126,241 input tokens (summed over the requests) and 11,590 output tokens. At the gateway prices of the group (5.0e-08 USD per input token and 1.92e-07 per output token, no cache credit) the step cost at most 0.11 USD; at the public list price of 3.0e-07 and 1.2e-06 it costs at most 0.65 USD. The run used the window 128000 of the local settings, not 256000.
- The gateway config sets `data_collection: deny` for the group, so a provider that stores or trains on prompts is skipped (SECURITY.md rule 13).

## Existing Tool Considered

The LiteLLM gateway and its hosted group `deepseek-v4.1-flash-1017`, the settings `ai.tasks.implement` and `roadmap.implement.ladder`, and the factory `get_tier_model` cover the need. The change builds no code. It deletes none.
