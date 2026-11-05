## MODIFIED Requirements

### Requirement: The failure classes
The failure taxonomy SHALL have these 18 classes: `provider`, `parser`, `test`, `lint`, `types`, `plan_defect`, `premise_false`, `oom`, `timeout`, `refused_tool`, `conflict`, `ci_infra`, `no_change_in_fix`, `tests_lost`, `head_moved`, `output_cap`, `read_only_path` and `limit_reached`.

#### Scenario: The class list
- **WHEN** a test reads the classes of the taxonomy
- **THEN** it finds these 18 and no other

### Requirement: One default action for each class
`ACTION_BY_CLASS` SHALL give each class exactly one default action: `provider`, `timeout`, `ci_infra`, `tests_lost` and `head_moved` `retry`; `parser` `change_tier`; `test`, `lint` and `types` `repair`; `plan_defect` `amend`; `premise_false` `return`; `oom`, `output_cap` and `limit_reached` `raise_limit`; `refused_tool`, `conflict`, `no_change_in_fix` and `read_only_path` `wait`.

#### Scenario: The table
- **WHEN** a test reads the table
- **THEN** its keys are the 18 classes and each value is the action above
