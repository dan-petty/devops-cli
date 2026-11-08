## MODIFIED Requirements

### Requirement: A step has a name
The module `failure.py` SHALL hold `StepName`, a string enum whose values are the steps that the jobs record: `plan` and `apply` (stage), `investigate` (refine) and `place` (intake). The values SHALL be unique one-word strings.

#### Scenario: The step names
- **WHEN** a test reads the values of `StepName`
- **THEN** it finds `plan`, `apply`, `investigate` and `place`, each once, and each one word
