## ADDED Requirements

### Requirement: An agent with a tool output sends tool choice auto to a Claude group
An agent with a tool output and no text output SHALL send `tool_choice: "auto"` and its tool list to a Claude group of the gateway, because the provider API refuses a forced tool choice for the model. It SHALL send `tool_choice: "required"` to every other model.

#### Scenario: The stage planner on a Claude group
- **WHEN** an agent with a tool output runs on `claude-sonnet-5-5` through the gateway
- **THEN** the request body has `tool_choice` `auto` and offers the tool `final_result`

#### Scenario: A model that is not a Claude group
- **WHEN** the same agent runs on `devops-chat` through the gateway
- **THEN** the request body has `tool_choice` `required`
