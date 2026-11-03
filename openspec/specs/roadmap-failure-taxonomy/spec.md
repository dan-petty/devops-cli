# roadmap-failure-taxonomy Specification

## Purpose
The failure taxonomy of the implement job: the 12 classes of a failure, the pure classifier that maps the evidence of a stop to one class, and the one table that gives each class its default action. The stop comment, the job record and the metrics of the roadmap use the class.

## Requirements

### Requirement: The failure classes
The failure taxonomy SHALL have these 12 classes: `provider`, `parser`, `test`, `lint`, `types`, `plan_defect`, `premise_false`, `oom`, `timeout`, `refused_tool`, `conflict` and `ci_infra`.

#### Scenario: The class list
- **WHEN** a test reads the classes of the taxonomy
- **THEN** it finds these 12 and no other

### Requirement: A pure classifier
`classify_failure` SHALL map the error text, the exit status, the refusal of a tool, the name of the check and the last message of the agent to one class, and SHALL read no file, make no request and change no state. Input that no rule matches SHALL be `ci_infra`.

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

#### Scenario: Unknown input
- **WHEN** the evidence is empty, or no rule matches
- **THEN** the class is `ci_infra`

### Requirement: Real excerpts map to their class
The table test of the classifier SHALL use the stop texts of the issues #2175, #2735 and #2747, and the failed-test text of #2924, and SHALL cover all 12 classes.

#### Scenario: The excerpts
- **WHEN** the table test runs offline
- **THEN** the `mypy` stop of #2175 is `types`, the tool retries of #2735 are `refused_tool`, the Ollama error of #2747 is `parser`, and the failed tests of #2924 are `test`

### Requirement: One default action for each class
`ACTION_BY_CLASS` SHALL give each class exactly one default action: `provider`, `timeout` and `ci_infra` `retry`; `parser` `change_tier`; `test`, `lint` and `types` `repair`; `plan_defect` `amend`; `premise_false` `return`; `oom` `raise_limit`; `refused_tool` and `conflict` `wait`.

#### Scenario: The table
- **WHEN** a test reads the table
- **THEN** its keys are the 12 classes and each value is the action above

### Requirement: The action left
`left_action` SHALL give the default action of the class, or `wait` when the action taken is that default.

#### Scenario: A repair that did not work
- **WHEN** the class is `types` and the job took `repair`
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
