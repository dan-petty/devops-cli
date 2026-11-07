## MODIFIED Requirements

### Requirement: The failure classes
The failure taxonomy SHALL have these 19 classes: `provider`, `parser`, `test`, `lint`, `types`, `plan_defect`, `premise_false`, `oom`, `timeout`, `refused_tool`, `conflict`, `ci_infra`, `no_change_in_fix`, `tests_lost`, `head_moved`, `output_cap`, `read_only_path`, `limit_reached` and `outside_plan`.

#### Scenario: The class list
- **WHEN** a test reads the classes of the taxonomy
- **THEN** it finds these 19 and no other

### Requirement: One default action for each class
`ACTION_BY_CLASS` SHALL give each class exactly one default action: `provider`, `timeout`, `ci_infra` and `head_moved` `retry`; `parser` `change_tier`; `test`, `lint` and `types` `repair`; `plan_defect` `amend`; `premise_false` `return`; `oom`, `output_cap` and `limit_reached` `raise_limit`; `refused_tool`, `conflict`, `no_change_in_fix`, `read_only_path`, `tests_lost` and `outside_plan` `wait`.

#### Scenario: The table
- **WHEN** a test reads the table
- **THEN** its keys are the 19 classes and each value is the action above

#### Scenario: A new runner image and a lost test
- **WHEN** an item stopped with the class `tests_lost`, and the digest in the template differs from the digest of its Job
- **THEN** the rule `digest` does not clear the stop
