## ADDED Requirements

### Requirement: The two settings of the decision points have variables
The variable `DEVOPS_CLI_AI_DECISION_MODEL` SHALL set `ai.decision_model`. The variable `DEVOPS_CLI_ROADMAP_DECISIONS` SHALL set `roadmap.decisions` from a JSON object of point names and modes, and `devops config set roadmap.decisions` SHALL take the same JSON object. A value that is no JSON object SHALL make the settings fail to load, and the error SHALL name the setting.

#### Scenario: The variable sets the mode of a point
- **WHEN** the settings load with `DEVOPS_CLI_ROADMAP_DECISIONS` set to `{"stage.verify_screen": "shadow"}` and `DEVOPS_CLI_AI_DECISION_MODEL` set to `typesafe/jev-1.14`
- **THEN** `roadmap.decisions` maps `stage.verify_screen` to `shadow` and `ai.decision_model` is `typesafe/jev-1.14`

#### Scenario: A value that is no JSON object
- **WHEN** the settings load with `DEVOPS_CLI_ROADMAP_DECISIONS` set to `shadow`
- **THEN** the load fails and the error names `roadmap.decisions`

### Requirement: The registry bounds the series of its catalogue
The registry SHALL refuse a catalogue of points whose label sets of `devops_cli_decision_point_total` are more than 60. A point SHALL list the label sets that it can write: the bands `continue`, `review` and `flag` for each resolver that it has besides the fallback, and `none` for the fallback, in the modes `shadow` and `on`.

#### Scenario: Too many points
- **WHEN** a test builds a registry of eight points that can each write 8 label sets
- **THEN** the registry raises an error that names the bound of 60
