## ADDED Requirements

### Requirement: The stage prompt names the active change as a blocker
The stage prompt SHALL tell the planner to read the requirements of each capability that its plan changes with the `read_spec` tool before it adds a requirement. It SHALL tell the planner to name the active change as a blocker in `dependencies` when another active change already adds or modifies the requirement whose behavior the plan needs.

#### Scenario: The rendered prompt holds the rule
- **WHEN** The stage prompt is rendered for a plan.
- **THEN** The prompt holds the instruction to read the requirements of the capability first and the rule to name the active change as a blocker.
