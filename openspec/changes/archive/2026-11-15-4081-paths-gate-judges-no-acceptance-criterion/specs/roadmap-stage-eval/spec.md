## MODIFIED Requirements

### Requirement: The replay fails when a gate stops refusing a known-bad plan
`devops roadmap eval stage --replay` SHALL run the recorded plan of each case through the gates `paths`, `kind` and `criteria`, with no model call and no git read. The gate `paths` SHALL be `check_proposal` with the capabilities of the case but the criteria rule, so it judges `missing_path`, `spec_delta_wrong` and `verify_form`. It SHALL exit 1 when a gate refuses no defect that names it, gives another path or message than the defect lists, or refuses a `good` plan. Otherwise it SHALL exit 0.

#### Scenario: Every gate refuses what it must
- **WHEN** the replay runs on the set
- **THEN** it exits 0 and prints, for each gate, the known defects and the defects it caught

#### Scenario: A gate stops refusing
- **WHEN** a plan of the set holds a missing path and the path is made a file of the recorded tree
- **THEN** the replay exits 1 and names the case and the gate

#### Scenario: A rule of the spec delta stops refusing
- **WHEN** the rule for a spec delta that the changed paths do not need refuses nothing
- **THEN** the replay exits 1 and names the case and the type `spec_delta_wrong`

#### Scenario: A good plan is refused
- **WHEN** a `good` plan is changed to name a path that its tree lacks
- **THEN** the replay exits 1 and names the case
