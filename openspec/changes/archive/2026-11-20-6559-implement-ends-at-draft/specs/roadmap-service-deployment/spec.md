## MODIFIED Requirements

### Requirement: The ConfigMap template holds the doubled implement limits
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL set each attempt limit of `roadmap.implement` to two times its code default, the two token budgets to four times, and the item time to the ceiling of the Job deadline.

#### Scenario: The implement limits are read
- **WHEN** the template is validated as settings
- **THEN** `repair_rounds`, `command_timeout_seconds`, `request_timeout_seconds`, `step_time_limit_seconds`, `deadline_stall_seconds`, `deadline_extension_seconds`, `digest_clears_per_class`, `digest_clears_per_item`, `continuations_per_item`, `max_requests`, `max_tool_calls`, `tool_retries`, `max_refusals`, `max_consecutive_refusals` and `model_resends` of `roadmap.implement` are each two times their `DEFAULT_` constant

#### Scenario: The item time of implement is read
- **WHEN** the template is validated as settings
- **THEN** `roadmap.implement.item_time_limit_seconds` equals `DEFAULT_ROADMAP_IMPLEMENT_DEADLINE_CEILING_SECONDS`

#### Scenario: The token budgets of implement are read
- **WHEN** the template is validated as settings
- **THEN** `step_token_budget` and `item_token_budget` of `roadmap.implement` are each four times their `DEFAULT_` constant
