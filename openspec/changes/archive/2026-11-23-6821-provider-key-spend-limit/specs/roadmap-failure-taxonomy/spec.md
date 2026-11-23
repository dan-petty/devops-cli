## MODIFIED Requirements

### Requirement: The failure classes
The failure taxonomy SHALL have these 24 classes: `provider`, `parser`, `test`, `lint`, `types`, `plan_defect`, `premise_false`, `oom`, `timeout`, `refused_tool`, `refused_reply`, `conflict`, `ci_infra`, `no_change_in_fix`, `tests_lost`, `head_moved`, `output_cap`, `read_only_path`, `limit_reached`, `outside_plan`, `git_config`, `plan_unreadable`, `form_check` and `spend_limit`.

#### Scenario: The class list
- **WHEN** a test reads the classes of the taxonomy
- **THEN** it finds these 24 and no other

#### Scenario: The class of a form check
- **WHEN** a test reads the default action of `form_check`
- **THEN** it is `retry`

### Requirement: One default action for each class
`ACTION_BY_CLASS` SHALL give each class exactly one default action: `provider`, `timeout`, `ci_infra`, `head_moved` and `form_check` `retry`; `parser` `change_tier`; `test`, `lint`, `types` and `conflict` `repair`; `plan_defect` `amend`; `premise_false` `return`; `oom`, `output_cap` and `limit_reached` `raise_limit`; `refused_tool`, `refused_reply`, `no_change_in_fix`, `read_only_path`, `tests_lost`, `outside_plan`, `git_config`, `plan_unreadable` and `spend_limit` `wait`.

#### Scenario: The table
- **WHEN** a test reads the table
- **THEN** its keys are the 24 classes and each value is the action above

#### Scenario: A new runner image and a lost test
- **WHEN** an item stopped with the class `tests_lost`, and the digest in the template differs from the digest of its Job
- **THEN** the rule `digest` does not clear the stop

### Requirement: An exception type gives a failure class
The module `failure.py` SHALL hold the tuple `CLASS_BY_EXCEPTION` of (exception type, failure class), most specific first, and `failure_class_of` SHALL return the class of the first entry that the exception matches by `isinstance`. The last entry SHALL be `DevOpsCLIError`.

#### Scenario: A mapped exception
- **WHEN** a test gives each mapped exception type to `failure_class_of`
- **THEN** `RoadmapPlanReadBackError` gives `plan_unreadable`, `RoadmapItemChangedError` gives `head_moved`, `StructuredOutputValidationError` gives `parser`, `AIKeySpendLimitError` gives `spend_limit`, `AIClientError` gives `provider`, `RoadmapStageError` gives `plan_defect`, and `GitHubOperationError`, `GitOperationError`, `ToolExecutionError` and `DevOpsCLIError` give `ci_infra`

#### Scenario: A specific type comes before its parent
- **WHEN** the exception is a `RoadmapPlanReadBackError`
- **THEN** the class is `plan_unreadable` and not `plan_defect`

#### Scenario: A subclass with no entry
- **WHEN** the exception is a subclass of a mapped type that has no entry of its own
- **THEN** the class is the class of its parent

### Requirement: A failure class has a wait
The module `failure.py` SHALL hold the read-only mapping `RETRY_AFTER` from each class that `CLASS_BY_EXCEPTION` gives to a `timedelta`: `provider` 1 hour, `parser` 6 hours, `plan_defect` 1 hour, `ci_infra` 1 hour, `head_moved` 0, `plan_unreadable` 6 hours and `spend_limit` 1 hour. The keys of `RETRY_AFTER` SHALL be exactly the classes of `CLASS_BY_EXCEPTION`, and no value SHALL be `None`.

#### Scenario: The keys
- **WHEN** a test reads the keys of `RETRY_AFTER` and the classes of `CLASS_BY_EXCEPTION`
- **THEN** the two sets are equal

#### Scenario: The waits
- **WHEN** a test reads the value of each key
- **THEN** it finds 1 hour for `provider`, `plan_defect`, `ci_infra` and `spend_limit`, 6 hours for `parser` and `plan_unreadable`, and 0 for `head_moved`

## ADDED Requirements

### Requirement: A spent provider key waits for a person
`classify_failure` SHALL give `spend_limit` to a text that holds the text of `AIKeySpendLimitError`, which the rule makes from `ERRORS.ai.provider_key_spend_limit`. That rule SHALL come before each other rule of the text, and after the rules of the pod and the exit status. A stop with the class `spend_limit` SHALL have the action `wait`, and SHALL NOT count toward `roadmap.stage.plan_defect_limit`.

#### Scenario: The log of a stage Job on a spent key
- **WHEN** the text is the log tail of a stage Job that holds an earlier line with `timed out` and ends with `Could not run the stage Job: The provider key reached its spend limit (HTTP 403). A person raises the spend limit of the key at the provider, or changes the key.`
- **THEN** the class is `spend_limit` and the action left is `wait`

#### Scenario: The raw text of the provider
- **WHEN** the text holds `Key limit exceeded` and no text of `AIKeySpendLimitError`
- **THEN** the class is not `spend_limit`

#### Scenario: A refused key
- **WHEN** the text is `Could not run the stage Job: The model refused the key (HTTP 403).`
- **THEN** the class is not `spend_limit`
