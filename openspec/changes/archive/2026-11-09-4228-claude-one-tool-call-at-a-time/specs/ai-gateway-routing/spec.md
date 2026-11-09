## ADDED Requirements

### Requirement: A request to a Claude group forbids parallel tool calls
The CLI SHALL set `parallel_tool_calls` to false on every request with tools to a Claude group of the gateway, so that the model makes one tool call per reply and the gateway joins no arguments of several calls into one JSON text. A request to a model that is not a Claude group SHALL set no `parallel_tool_calls`.

#### Scenario: A request to a Claude group
- **WHEN** an agent with a tool output sends a request to `claude-sonnet-5-5` through the gateway
- **THEN** the request body holds `parallel_tool_calls` with the value false

#### Scenario: A request to another model
- **WHEN** an agent sends a request to `devops-chat` or to `deepseek-v4.1-flash-1017` through the gateway
- **THEN** the request body holds no `parallel_tool_calls`
