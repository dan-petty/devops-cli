## ADDED Requirements

### Requirement: A spec that the archive validation refuses is a plan defect
When `uv run devops openspec archive <change>` exits with status 1 after it moved the change folder into the archive, the strict validation of the specs refused a spec of the plan. The stop SHALL pass the class `plan_defect`, so the action left is `amend`. The words of the output, as `1 failed`, SHALL NOT decide the class. An archive that fails before it moves the folder SHALL keep the class that the classifier gives.

#### Scenario: The validation refuses a long requirement
- **WHEN** the archive moves the change folder, then exits 1 with `Totals: 258 passed, 1 failed (259 items)` and a requirement text longer than 500 characters
- **THEN** the item stops at the archive, `implement.failure` is `plan_defect`, and the comment names the action left `amend` and the spec that failed

#### Scenario: An archive that keeps the change folder
- **WHEN** the archive exits 1 with `openspec: the change has no delta` and the change folder stays in place
- **THEN** the item stops at the archive with the class `ci_infra`
