## MODIFIED Requirements

### Requirement: The golden set holds the plans with their defects
The set SHALL hold one folder under `tests/fixtures/roadmap_eval/stage/` for each case: the issue text, the plan, the facts of the tree that the gates need, and the known defects. It SHALL hold the 37 plans of 2026-11-01 and at least 3 cases with the verdict `good` and no defect. A defect SHALL have a type from the shared enum, the review text with its evidence, and the gate that must refuse it: `paths`, `kind`, `pending` or `none`. A defect with the gate `none` whose type was once planned for a gate SHALL give a `reason` that says why the recorded plan cannot show it to a gate.

#### Scenario: The set loads
- **WHEN** the set is loaded
- **THEN** it holds at least 40 cases, at least 3 of them `good`, and each defect has one of the nine types

#### Scenario: A case that does not match the model
- **WHEN** a case folder has a defect with a type that is not in the enum
- **THEN** loading fails with an error that names the case

#### Scenario: A defect that no gate can judge says why
- **WHEN** the set is loaded
- **THEN** each defect of the types `ignores_existing_code`, `spec_delta_wrong`, `verify_form` and `task_order` that has the gate `none` has a `reason`, and each of them that has the gate `paths` holds the `message` of the problem

### Requirement: The replay fails when a gate stops refusing a known-bad plan
`devops roadmap eval stage --replay` SHALL run the recorded plan of each case through the gates `paths`, `kind` and `criteria`, with no model call and no read of git. The gate `paths` SHALL be `check_proposal`, with the capabilities of the case: the path rule, the rules of the spec delta and the form rule, so it judges defects of the types `missing_path`, `spec_delta_wrong` and `verify_form`. It SHALL exit 1 when a gate no longer refuses a defect that names it, when a gate does not name a path or give the message that the defect lists, or when a gate refuses a `good` plan. Otherwise it SHALL exit 0.

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

### Requirement: A defect for a gate that does not exist yet is listed, not failed
A defect with the gate `pending` SHALL be listed with its type and the issue of the gate, and SHALL fail nothing, for a type in `PENDING_GATES`. A defect with the gate `none` SHALL be counted as judged by no gate. When a gate exists for the type of a `pending` defect, or no gate is planned for it, the replay SHALL fail and say to set the gate of the defect. The list of types that wait for a gate SHALL print only when a type waits.

#### Scenario: Pending defects
- **WHEN** the replay runs on the set
- **THEN** the output has no list of types that wait for a gate, and the exit code is 0

#### Scenario: A false premise is judged by no gate
- **WHEN** the replay runs on the set
- **THEN** the defects of the type `false_premise` are counted as judged by no gate, and the exit code is 0

#### Scenario: A gate arrives
- **WHEN** a `pending` defect has the type of a gate that exists
- **THEN** the replay exits 1 and says that the case file must name the gate

## ADDED Requirements

### Requirement: The replay counts the defects by type
The replay SHALL print, for each type of defect that the set holds, the defects a gate caught, the defects it missed, the defects that wait for a gate, the defects that no gate judges, and the total. It SHALL then print the share of all known defects that a gate judges, caught or missed. The JSON report SHALL hold the same counts and the number of defects judged and known.

#### Scenario: The counts by type
- **WHEN** the replay runs on the set
- **THEN** it prints a row for each type, with `verify_form` caught 4, missed 0 and judged by no gate 12, and the line `Defects that a gate judges: 64 of 299 (21%).`

#### Scenario: The counts as JSON
- **WHEN** the replay runs with `--json`
- **THEN** the report holds `defects` with `judged` 64 and `known` 299, and a row for each type
