## MODIFIED Requirements

### Requirement: The failure classes
The failure taxonomy SHALL have these 23 classes: `provider`, `parser`, `test`, `lint`, `types`, `plan_defect`, `premise_false`, `oom`, `timeout`, `refused_tool`, `refused_reply`, `conflict`, `ci_infra`, `no_change_in_fix`, `tests_lost`, `head_moved`, `output_cap`, `read_only_path`, `limit_reached`, `outside_plan`, `git_config`, `plan_unreadable` and `form_check`.

#### Scenario: The class list
- **WHEN** a test reads the classes of the taxonomy
- **THEN** it finds these 23 and no other

#### Scenario: The class of a form check
- **WHEN** a test reads the default action of `form_check`
- **THEN** it is `retry`
