## MODIFIED Requirements

### Requirement: A defect for a gate that does not exist yet is listed, not failed
A defect with the gate `pending` SHALL be listed with its type and the issue of the gate, and SHALL fail nothing. A defect with the gate `none` SHALL be listed as judged by no gate. When a gate exists for the type of a `pending` defect, the replay SHALL fail and say to set the gate of the defect.

#### Scenario: Pending defects
- **WHEN** the replay runs on the set
- **THEN** the output lists the types `ignores_existing_code`, `spec_delta_wrong`, `verify_form`, `task_order` and `criterion_dropped` with their counts, and the exit code is 0

#### Scenario: A false premise is judged by no gate
- **WHEN** the replay runs on the set
- **THEN** the defects of the type `false_premise` are listed as judged by no gate, and the exit code is 0

#### Scenario: A gate arrives
- **WHEN** a `pending` defect has the type of a gate that exists
- **THEN** the replay exits 1 and says that the case file must name the gate
