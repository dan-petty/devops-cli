## ADDED Requirements

### Requirement: A request to a Claude group carries an output cap
The CLI SHALL set `max_tokens` on every request to a Claude group of the gateway, to a value above the Anthropic default of 4096 output tokens, so that the reply of a stage plan is not cut. A request to a model that is not a Claude group SHALL set no `max_tokens`, and keeps the limit of its gateway entry.

#### Scenario: A request to a Claude group
- **WHEN** an agent with a tool output sends a request to `claude-sonnet-5-5` through the gateway
- **THEN** the request body holds an output token limit above 4096

#### Scenario: A request to another model
- **WHEN** an agent sends a request to `devops-chat` or to `deepseek-v4.1-flash-1017` through the gateway
- **THEN** the request body holds no output token limit
