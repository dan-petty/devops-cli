## MODIFIED Requirements

### Requirement: A step has a name
The module `failure.py` SHALL hold `StepName`, a string enum whose values are the steps that the jobs name: `plan` and `apply` (stage), `investigate` (refine), `place` (intake), and `select`, `gate` and `review` (the other steps of the stage round, which only the metric `devops_cli_roadmap_step_seconds` names). A failed job SHALL record only a step that it records today; a stored step SHALL stay a string that `StepName` reads. The values SHALL be unique one-word strings.

#### Scenario: The step names
- **WHEN** a test reads the values of `StepName`
- **THEN** it finds `plan`, `apply`, `investigate`, `place`, `select`, `gate` and `review`, each once, and each one word

#### Scenario: An old record
- **WHEN** a record of a failed stage item holds the step `plan` written before the new members existed
- **THEN** the step is a member of `StepName` and the item waits for the time of its failure class
