# Spec Delta

## MODIFIED Requirements

### Requirement: Jev decides the proposal fields
With `roadmap.intake.jev` set to `on`, intake SHALL ask Jev, in one request, for the type of a candidate whose title and issue give none, for its priority, Value and Effort, and for a yes/no answer for each nearest item. The answers SHALL make the same `ModelProposal` that the `triage` model returns, so the checks of intake decide which values stand. With the setting `off`, intake SHALL not call Jev. The setting SHALL be `off`, `shadow` or `on`, and `off` SHALL be the default.

#### Scenario: Jev gives the fields
- **WHEN** the setting is `on` and Jev answers with a confidence of 0.90 or more
- **THEN** the proposal holds the type, priority, Value and Effort of the answers and the `triage` model is not called

#### Scenario: The title gives the type
- **WHEN** the title of the candidate has a Conventional Commit type
- **THEN** the request holds no type question

#### Scenario: The setting is off
- **WHEN** the setting is `off`
- **THEN** `build_intake_model()` returns the model of the `intake` task and no Jev request is made

#### Scenario: The old bool is refused
- **WHEN** the setting is the bool `true`
- **THEN** the settings fail to validate

#### Scenario: The variable sets the mode
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_INTAKE_JEV` is `shadow`
- **THEN** the loaded setting is `shadow`
