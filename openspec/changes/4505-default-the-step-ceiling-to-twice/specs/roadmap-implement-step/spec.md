## MODIFIED Requirements

### Requirement: The ceiling of a step budget is a setting
The setting `roadmap.implement.step_token_ceiling` SHALL set the most tokens, in the unit of `step_token_budget`, that a step may reach with its one extension. It SHALL have the variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_STEP_TOKEN_CEILING`. When no config file and no variable sets it, the ceiling SHALL be twice the loaded `step_token_budget`. A ceiling below `roadmap.implement.step_token_budget` SHALL be refused.

#### Scenario: The default ceiling
- **WHEN** no config file and no variable sets the ceiling or the step budget
- **THEN** the ceiling is twice the default step budget

#### Scenario: A step budget above the old fixed ceiling
- **WHEN** the config file sets `step_token_budget` to 17000000 and sets no ceiling
- **THEN** the settings load and the ceiling is 34000000

#### Scenario: A variable for the step budget only
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_STEP_TOKEN_BUDGET` holds 17000000 and nothing sets the ceiling
- **THEN** the settings load and the ceiling is 34000000

#### Scenario: The whole extension
- **WHEN** `step_token_budget` is 12000000, nothing sets the ceiling, and the step makes progress at its budget
- **THEN** the extension holds a budget of 18000000 tokens and says that the ceiling did not cut it

#### Scenario: A variable for the ceiling
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_STEP_TOKEN_CEILING` holds 9000000
- **THEN** the ceiling is 9000000

#### Scenario: A ceiling below the step budget
- **WHEN** the config file sets `step_token_budget` to 5000 and `step_token_ceiling` to 4999
- **THEN** loading the settings fails and the message names `step_token_ceiling`
