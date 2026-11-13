## ADDED Requirements

### Requirement: A Claude group caches its prompt prefix
A Claude group SHALL set `cache_control_injection_points` in its `litellm_params` with a point on the system messages (`location: message`, `role: system`) and a point on the last message (`location: message`, `index: -1`), and with at most the 4 points that Anthropic allows. No other group SHALL set `cache_control_injection_points`.

#### Scenario: The cache points of the Claude groups
- **WHEN** the gateway test reads `k8s/llm/gateway/config.yaml`
- **THEN** `claude-sonnet-5-5` and `claude-haiku-5-5` each hold the system point and the last-message point, and the hosted-group check reports no problem

#### Scenario: A Claude group loses its cache points
- **WHEN** a test edit removes `cache_control_injection_points` from `claude-sonnet-5-5`
- **THEN** the hosted-group check reports that `claude-sonnet-5-5` caches no system prompt

#### Scenario: A Claude group loses its last-message point
- **WHEN** a test edit removes the point with `index: -1` from `claude-haiku-5-5`
- **THEN** the hosted-group check reports that `claude-haiku-5-5` caches no history of an agent run

#### Scenario: A Claude group sets more points than Anthropic allows
- **WHEN** a test edit gives `claude-haiku-5-5` five points
- **THEN** the hosted-group check reports that `claude-haiku-5-5` sets more cache points than Anthropic allows

#### Scenario: Another group sets a cache point
- **WHEN** a test edit gives `deepseek-v4.1-flash-1017` a cache point
- **THEN** the hosted-group check reports that only a Claude group sets cache points
