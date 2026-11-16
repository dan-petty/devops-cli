# Spec Delta: roadmap-service-deployment

## MODIFIED Requirements

### Requirement: Every chat model slot of the Service names one model except analysis
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL name `openrouter/deepseek/deepseek-v4.1-flash-1017` for `ai.model` and each chat task, and `local/qwen3.8:27b` for the tasks `triage` and `analysis`. Comments in the template SHALL give the reason and the date of each departure from the hosted model. The template SHALL NOT name `claude-sonnet-5-5` for any chat slot.

#### Scenario: The rendered template is read
- **WHEN** the ConfigMap is rendered from the repository's template and validated as settings
- **THEN** `ai.model` and the model of each task except `embedding`, `triage` and `analysis`, with its parent task applied, are `openrouter/deepseek/deepseek-v4.1-flash-1017`, the model of the tasks `triage` and `analysis` is `local/qwen3.8:27b`, and the model of the task `embedding` is `local/qwen3-embedding:0.6b`

#### Scenario: The window of analysis is the window of the trial
- **WHEN** the template is read
- **THEN** the `context_window` of the tasks `analysis` and `stage` is 256000, and it is not above the `max_input_tokens` of the group of each task in `k8s/llm/gateway/config.yaml`

#### Scenario: The comment of the trial is read
- **WHEN** the lines above the task `analysis` in the template are read
- **THEN** they name #4369, the date 2026-11-10, 67 USD a week, #3874, Sonnet as a later trial, and the local trial of 2026-11-16

## ADDED Requirements

### Requirement: The ConfigMap template holds the doubled stage limits
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL set each attempt limit of `roadmap.stage` to two times its code default.

#### Scenario: The stage limits are read
- **WHEN** the template is validated as settings
- **THEN** `verify_repair_rounds`, `verify_repair_rounds_ceiling`, `gate_returns`, `gate_return_extensions`, `plan_defect_limit`, `max_requests` and `max_tool_calls` of `roadmap.stage` are each two times their `DEFAULT_` constant

### Requirement: The ConfigMap template holds the doubled implement limits
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL set each attempt limit of `roadmap.implement` to two times its code default, and the item time to the ceiling of the Job deadline.

#### Scenario: The implement limits are read
- **WHEN** the template is validated as settings
- **THEN** `repair_rounds`, `step_token_budget`, `item_token_budget`, `command_timeout_seconds`, `request_timeout_seconds`, `monitor_timeout_seconds`, `step_time_limit_seconds`, `deadline_stall_seconds`, `deadline_extension_seconds`, `digest_clears_per_class`, `digest_clears_per_item`, `continuations_per_item`, `max_requests`, `max_tool_calls`, `tool_retries`, `max_refusals`, `max_consecutive_refusals` and `model_resends` of `roadmap.implement` are each two times their `DEFAULT_` constant

#### Scenario: The item time of implement is read
- **WHEN** the template is validated as settings
- **THEN** `roadmap.implement.item_time_limit_seconds` equals `DEFAULT_ROADMAP_IMPLEMENT_DEADLINE_CEILING_SECONDS`

### Requirement: The ConfigMap template holds the doubled fix-plan limits
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL set `time_budget_seconds`, `head_attempts` and `revisions` of `roadmap.fix_plan` to two times their code defaults.

#### Scenario: The fix-plan limits are read
- **WHEN** the template is validated as settings
- **THEN** `time_budget_seconds`, `head_attempts` and `revisions` of `roadmap.fix_plan` are each two times their `DEFAULT_` constant
