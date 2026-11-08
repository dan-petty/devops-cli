## ADDED Requirements

### Requirement: An exception type gives a failure class
The module `failure.py` SHALL hold the tuple `CLASS_BY_EXCEPTION` of (exception type, failure class), most specific first, and `failure_class_of` SHALL return the class of the first entry that the exception matches by `isinstance`. The last entry SHALL be `DevOpsCLIError`.

#### Scenario: A mapped exception
- **WHEN** a test gives each mapped exception type to `failure_class_of`
- **THEN** `RoadmapItemChangedError` gives `head_moved`, `StructuredOutputValidationError` gives `parser`, `AIClientError` gives `provider`, `RoadmapStageError` gives `plan_defect`, and `GitHubOperationError`, `GitOperationError`, `ToolExecutionError` and `DevOpsCLIError` give `ci_infra`

#### Scenario: A specific type comes before its parent
- **WHEN** the exception is a `RoadmapItemChangedError` or a `StructuredOutputValidationError`
- **THEN** the class is `head_moved` or `parser`, and not the class of `GitHubOperationError` or `AIClientError`

#### Scenario: A subclass with no entry
- **WHEN** the exception is a subclass of a mapped type that has no entry of its own
- **THEN** the class is the class of its parent

### Requirement: A step has a name
The module `failure.py` SHALL hold `StepName`, a string enum whose values are the steps that the stage records: `plan` and `apply`. The values SHALL be unique one-word strings.

#### Scenario: The step names
- **WHEN** a test reads the values of `StepName`
- **THEN** it finds `plan` and `apply`, each once, and each one word
