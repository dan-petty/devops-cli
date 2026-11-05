## MODIFIED Requirements

### Requirement: The failure classes
The failure taxonomy SHALL have these 19 classes: `provider`, `parser`, `test`, `lint`, `types`, `plan_defect`, `premise_false`, `oom`, `timeout`, `refused_tool`, `conflict`, `ci_infra`, `no_change_in_fix`, `not_ticked`, `tests_lost`, `head_moved`, `output_cap`, `read_only_path` and `limit_reached`.

#### Scenario: The class list
- **WHEN** a test reads the classes of the taxonomy
- **THEN** it finds these 19 and no other

### Requirement: One default action for each class
`ACTION_BY_CLASS` SHALL give each class exactly one default action: `provider`, `timeout`, `ci_infra`, `tests_lost` and `head_moved` `retry`; `parser` `change_tier`; `test`, `lint` and `types` `repair`; `plan_defect` and `not_ticked` `amend`; `premise_false` `return`; `oom`, `output_cap` and `limit_reached` `raise_limit`; `refused_tool`, `conflict`, `no_change_in_fix` and `read_only_path` `wait`.

#### Scenario: The table
- **WHEN** a test reads the table
- **THEN** its keys are the 19 classes and each value is the action above

## ADDED Requirements

### Requirement: A spent budget asks for a higher limit
A stop with the class `limit_reached` SHALL have the action `raise_limit`.

#### Scenario: A spent budget
- **WHEN** a step stops because it spent `roadmap.implement.step_token_budget`
- **THEN** the class of the stop is `limit_reached` and the action left is `raise_limit`
