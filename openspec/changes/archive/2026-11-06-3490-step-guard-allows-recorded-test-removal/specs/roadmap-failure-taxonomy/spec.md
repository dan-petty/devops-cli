## MODIFIED Requirements

### Requirement: One default action for each class
`ACTION_BY_CLASS` SHALL give each class exactly one default action: `provider`, `timeout`, `ci_infra` and `head_moved` `retry`; `parser` `change_tier`; `test`, `lint` and `types` `repair`; `plan_defect` `amend`; `premise_false` `return`; `oom`, `output_cap` and `limit_reached` `raise_limit`; `refused_tool`, `conflict`, `no_change_in_fix`, `read_only_path` and `tests_lost` `wait`.

#### Scenario: The table
- **WHEN** a test reads the table
- **THEN** its keys are the 18 classes and each value is the action above

#### Scenario: A new runner image and a lost test
- **WHEN** an item stopped with the class `tests_lost`, and the digest in the template differs from the digest of its Job
- **THEN** the rule `digest` does not clear the stop
