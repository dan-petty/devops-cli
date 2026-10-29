# Spec Delta

## ADDED Requirements

### Requirement: The implement task serves the step with devops-coder
`ai.tasks.implement` SHALL default to the model `devops-coder` and the `context_window` 128000. `get_task_model("implement")` SHALL return the model of that task, so a config file or a variable that sets another model or window for the task changes the step.

#### Scenario: The defaults
- **WHEN** the settings load with no `ai.tasks.implement` key
- **THEN** `ai.for_task("implement")` has the model `devops-coder` and the `context_window` 128000

#### Scenario: A window set in the config file
- **WHEN** the project config file holds `ai.tasks.implement.context_window: 64000` and the settings load
- **THEN** `ai.for_task("implement").context_window` is 64000 and its model is still `devops-coder`
