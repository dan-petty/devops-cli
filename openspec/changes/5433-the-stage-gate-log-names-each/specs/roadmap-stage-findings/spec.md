## ADDED Requirements

### Requirement: A refused reply logs each of its findings

After the `stage gate returns` line, the stage job SHALL log one `stage gate refused finding` line for each of the first 20 findings of the last refused reply, with its place, the count of all findings, its gate, its code and its subject. The `stage gate returns` line SHALL keep its fields.

#### Scenario: The trace gate refuses two paths
- **WHEN** the last refused reply of an item has two findings of the code `stage_problem_trace_path`
- **THEN** two `stage gate refused finding` lines give `finding=1/2` and `finding=2/2`, the gate `trace`, the code and the path of each finding as the subject

#### Scenario: A reply has 25 findings
- **WHEN** the last refused reply of an item has 25 findings
- **THEN** 20 lines give `finding=1/25` to `finding=20/25`

### Requirement: The subject of a finding is masked and cut

The subject SHALL be the value of the field `path`, `tool` or `command` of the template of the code, in that order, or `none`. The line SHALL mask the subject with `mask_secrets` before it keeps the first 200 characters, and SHALL hold no other text of the plan, of the finding or of the model.

#### Scenario: A subject holds a token
- **WHEN** the path of a finding holds a GitHub token, and the token goes past character 200
- **THEN** the line gives the masked path cut to 200 characters, and no part of the token

#### Scenario: A finding names no subject
- **WHEN** the title check refuses a reply
- **THEN** the line of its finding gives `subject=none`
