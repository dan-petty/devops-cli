## MODIFIED Requirements

### Requirement: A step has a name
The module `failure.py` SHALL hold `StepName`, a string enum of the steps that the jobs name: `plan`, `apply`, `investigate`, `place`, and the steps that only the metric `devops_cli_roadmap_step_seconds` names. A failed job SHALL record only a step that it records today. A stored step SHALL stay a string that `StepName` reads. The values SHALL be unique one-word strings.

#### Scenario: The step names
- **WHEN** a test reads the values of `StepName`
- **THEN** it finds `plan`, `apply`, `investigate`, `place`, `select`, `gate`, `review`, `checks` and `publish`, each once, and each one word
- **AND** only the metric names `select`, `gate`, `review`, `checks` and `publish`

#### Scenario: An old record
- **WHEN** a record of a failed stage item holds the step `plan` written before the new members existed
- **THEN** the step is a member of `StepName` and the item waits for the time of its failure class
