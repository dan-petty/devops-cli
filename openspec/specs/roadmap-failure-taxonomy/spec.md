# roadmap-failure-taxonomy Specification

## Purpose
The failure taxonomy of the implement job: the 12 classes of a failure, the pure classifier that maps the evidence of a stop to one class, and the one table that gives each class its default action. The stop comment, the job record and the metrics of the roadmap use the class.

## Requirements

### Requirement: The failure classes
The failure taxonomy SHALL have these 19 classes: `provider`, `parser`, `test`, `lint`, `types`, `plan_defect`, `premise_false`, `oom`, `timeout`, `refused_tool`, `conflict`, `ci_infra`, `no_change_in_fix`, `tests_lost`, `head_moved`, `output_cap`, `read_only_path`, `limit_reached` and `outside_plan`.

#### Scenario: The class list
- **WHEN** a test reads the classes of the taxonomy
- **THEN** it finds these 19 and no other

### Requirement: A pure classifier
`classify_failure` SHALL map the error text, the exit status, the refusal of a tool, the name of the check and the log of the check to one class, and SHALL read no file, make no request and change no state. It SHALL NOT read the last message of the agent. Input that no rule matches SHALL be `ci_infra`.

#### Scenario: A provider error
- **WHEN** the text holds `ModelHTTPError: HTTP 503`
- **THEN** the class is `provider`

#### Scenario: The parser beats the provider
- **WHEN** the text holds the HTTP 400 of Ollama (`Ollama_chatException`)
- **THEN** the class is `parser`

#### Scenario: A signal exit status
- **WHEN** the exit status is 137
- **THEN** the class is `oom`, whatever the text says

#### Scenario: A check name with no sign in the log
- **WHEN** the text is "The check Test Job Duration failed." and the check is `Test Job Duration`
- **THEN** the class is `ci_infra`

#### Scenario: The log of a check
- **WHEN** the text is empty and the log of the check holds `ruff-check....Failed`
- **THEN** the class is `lint`

#### Scenario: A claim of the agent
- **WHEN** a test searches the fields of the evidence for the last message of the agent
- **THEN** it finds none, and a text that says "already implemented" in a stop for another cause gives that cause

#### Scenario: Unknown input
- **WHEN** the evidence is empty, or no rule matches
- **THEN** the class is `ci_infra`

### Requirement: Real excerpts map to their class
The table test of the classifier SHALL use the stop texts of the issues #2175, #2735 and #2747, the failed-test text of #2924, and synthetic stop texts that follow the stop patterns of #3476, and SHALL cover all 17 classes.

#### Scenario: The excerpts
- **WHEN** the table test runs offline
- **THEN** the `mypy` stop of #2175 is `types`, the tool retries of #2735 are `refused_tool`, the Ollama error of #2747 is `parser`, the failed tests of #2924 are `test`, and each synthetic stop has the class of its pattern

### Requirement: One default action for each class
`ACTION_BY_CLASS` SHALL give each class exactly one default action: `provider`, `timeout`, `ci_infra` and `head_moved` `retry`; `parser` `change_tier`; `test`, `lint` and `types` `repair`; `plan_defect` `amend`; `premise_false` `return`; `oom`, `output_cap` and `limit_reached` `raise_limit`; `refused_tool`, `conflict`, `no_change_in_fix`, `read_only_path`, `tests_lost` and `outside_plan` `wait`.

#### Scenario: The table
- **WHEN** a test reads the table
- **THEN** its keys are the 19 classes and each value is the action above

#### Scenario: A new runner image and a lost test
- **WHEN** an item stopped with the class `tests_lost`, and the digest in the template differs from the digest of its Job
- **THEN** the rule `digest` does not clear the stop

### Requirement: The action left
`left_action` SHALL give the default action of the class, or `wait` when the action taken is that default.

#### Scenario: A repair that did not work
- **WHEN** the class is `types` and the job took `repair`
- **THEN** the action left is `wait`

#### Scenario: A tier change that did not work
- **WHEN** the class is `parser` and the job took `change_tier`
- **THEN** the action left is `wait`

#### Scenario: No action taken
- **WHEN** the class is `oom` and the job took no action
- **THEN** the action left is `raise_limit`

### Requirement: A refused verification command is a refused tool
The classifier SHALL give the class `refused_tool` to the text of a stop that starts with the message in which the step refused a verification command, for a program, an option, a shape or a length. It SHALL read this rule before the rules for the other causes, whatever words the command or the reason holds. The rule SHALL follow the message of the step. The default action of the class SHALL stay `wait`.

#### Scenario: A refused program
- **WHEN** a step refuses the verification command `curl http://example.com`, and the reason lists `mypy` and `ruff` among the allowed programs
- **THEN** the class is `refused_tool` and the action is `wait`

#### Scenario: A refused option and a refused shape
- **WHEN** a step refuses `! git grep -O name src/`, `! git grep -n name src/ | cat` or a command longer than 2000 characters
- **THEN** the class is `refused_tool` and the action is `wait`

#### Scenario: A command that ran and failed
- **WHEN** the stop reason says that `uv run mypy --strict -- a.py` exited with status 1
- **THEN** the class is `types`

#### Scenario: A command with the words of another cause
- **WHEN** a step refuses `python -m pytest tests/roadmap/test_rate_limit.py`, or a search for `timed out`, `out of memory` or `merge conflict`
- **THEN** the class is `refused_tool` and the action is `wait`

### Requirement: A stop on a read-only path is not retried
A stop whose text holds `Read-only file system` or `EROFS` SHALL have the class `read_only_path` and the action `wait`. It SHALL NOT have the class `ci_infra` or the action `retry`, and the rule `digest` SHALL NOT clear it on a new runner image.

#### Scenario: A read-only path error
- **WHEN** a command of the job stops with `OSError: [Errno 30] Read-only file system`
- **THEN** the class of the stop is `read_only_path` and the action left is `wait`

#### Scenario: A new runner image
- **WHEN** an item is Blocked with the class `read_only_path` and the template names a new digest
- **THEN** the item stays Blocked until a trusted `implement: retry`

### Requirement: A spent budget asks for a higher limit
A stop with the class `limit_reached` SHALL have the action `raise_limit`.

#### Scenario: A spent budget
- **WHEN** a step stops because it spent `roadmap.implement.step_token_budget`
- **THEN** the class of the stop is `limit_reached` and the action left is `raise_limit`

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
The module `failure.py` SHALL hold `StepName`, a string enum whose values are the steps that the jobs record: `plan` and `apply` (stage), `investigate` (refine) and `place` (intake). The values SHALL be unique one-word strings.

#### Scenario: The step names
- **WHEN** a test reads the values of `StepName`
- **THEN** it finds `plan`, `apply`, `investigate` and `place`, each once, and each one word

### Requirement: A failure class has a wait
The module `failure.py` SHALL hold the read-only mapping `RETRY_AFTER` from each class that `CLASS_BY_EXCEPTION` gives to a `timedelta`: `provider` 1 hour, `parser` 6 hours, `plan_defect` 6 hours, `ci_infra` 1 hour and `head_moved` 0. The keys of `RETRY_AFTER` SHALL be exactly the classes of `CLASS_BY_EXCEPTION`, and no value SHALL be `None`.

#### Scenario: The keys
- **WHEN** a test reads the keys of `RETRY_AFTER` and the classes of `CLASS_BY_EXCEPTION`
- **THEN** the two sets are equal

#### Scenario: The waits
- **WHEN** a test reads the value of each key
- **THEN** it finds 1 hour for `provider` and `ci_infra`, 6 hours for `parser` and `plan_defect`, and 0 for `head_moved`
