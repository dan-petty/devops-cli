## ADDED Requirements

### Requirement: The style rules ask for the bottom line in the first line

`src/devops_cli/ai/tasks/style_ste100.md` SHALL ask for the bottom line in the first line of a reply, with each gate that still applies. A gate is any hold, blocker, review, person step, merge order or deployment step. The request that `with_style_request` adds to the system prompt of a model call SHALL hold this rule.

#### Scenario: A model call carries the first-line rule
- **WHEN** `with_style_request` builds the system prompt of a model call
- **THEN** the prompt asks for what to do or not do, the real state and each gate in the first line
- **AND** the prompt tells the model not to start with "done", "green" or "ready" while a gate applies
- **AND** the prompt asks a reply with many items to say in the first line which item to act on now and which item to hold
