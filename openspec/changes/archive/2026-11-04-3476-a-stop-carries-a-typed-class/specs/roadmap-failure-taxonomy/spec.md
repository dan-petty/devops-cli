## MODIFIED Requirements

### Requirement: The failure classes
The failure taxonomy SHALL have these 17 classes: `provider`, `parser`, `test`, `lint`, `types`, `plan_defect`, `premise_false`, `oom`, `timeout`, `refused_tool`, `conflict`, `ci_infra`, `no_change_in_fix`, `not_ticked`, `tests_lost`, `head_moved` and `output_cap`.

#### Scenario: The class list
- **WHEN** a test reads the classes of the taxonomy
- **THEN** it finds these 17 and no other

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
`ACTION_BY_CLASS` SHALL give each class exactly one default action: `provider`, `timeout`, `ci_infra`, `tests_lost` and `head_moved` `retry`; `parser` `change_tier`; `test`, `lint` and `types` `repair`; `plan_defect` and `not_ticked` `amend`; `premise_false` `return`; `oom` and `output_cap` `raise_limit`; `refused_tool`, `conflict` and `no_change_in_fix` `wait`.

#### Scenario: The table
- **WHEN** a test reads the table
- **THEN** its keys are the 17 classes and each value is the action above
