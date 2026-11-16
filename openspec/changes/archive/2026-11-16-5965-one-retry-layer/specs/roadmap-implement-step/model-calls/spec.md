## REMOVED Requirements

### Requirement: A model reply has an output cap and a call has a deadline
**Reason**: It held the deadline of a step call below the router timeout of the gateway, so the client ended a stuck call before the gateway could retry it or fall back (#5965). The gateway owns the retries now, and its attempt ends first.
**Migration**: None for a caller: the agent of a step sets the same model settings. The requirements "A model reply has an output cap and a call has a deadline inside the step" and "The deadline of a step call nests between the router timeout and the step limit" hold the rule.

## ADDED Requirements

### Requirement: A model reply has an output cap and a call has a deadline inside the step
The agent of a step SHALL set the model settings `max_tokens` to the context window of the task divided by `CONST_ROADMAP_IMPLEMENT_OUTPUT_WINDOW_SHARE`, and `request_timeout` to the setting `roadmap.implement.request_timeout_seconds`. A call that runs past the deadline SHALL end the step as stopped, and the model SHALL get no second request for it.

#### Scenario: The settings of the first request
- **WHEN** the step makes its first model request
- **THEN** the model settings of the request hold the cap, a quarter of the window, and the deadline of the setting

#### Scenario: The cap reaches the wire
- **WHEN** the agent of a step sends a request to an OpenAI chat model
- **THEN** the body of the request holds `max_completion_tokens` with the value of the cap, and no `request_timeout`

#### Scenario: A call that never ends
- **WHEN** a model call does not answer within the deadline
- **THEN** the step reports stopped with a reason that starts with `ModelRequestTimeout: ` and holds the deadline, the model got one request, and the checkout is reset

### Requirement: The deadline of a step call nests between the router timeout and the step limit
The timeout of the router in `k8s/llm/gateway/config.yaml` SHALL be less than the default of `roadmap.implement.request_timeout_seconds`, so the gateway ends a stuck attempt and can retry it or fall back first. The settings SHALL refuse a deadline above `roadmap.implement.step_time_limit_seconds`.

#### Scenario: The router timeout is short of the deadline
- **WHEN** a test reads `router_settings.timeout` of the gateway config
- **THEN** that timeout is less than the default of the deadline

#### Scenario: A deadline above the step limit
- **WHEN** the config sets `roadmap.implement.request_timeout_seconds` above `roadmap.implement.step_time_limit_seconds`
- **THEN** the settings load fails with an error that names both settings
