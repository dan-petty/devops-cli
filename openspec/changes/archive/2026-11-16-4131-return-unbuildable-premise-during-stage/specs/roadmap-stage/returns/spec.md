## ADDED Requirements

### Requirement: Every return writer calls apply_return
Every return writer in the stage subsystem SHALL call `apply_return` to return an item to New. The return writer SHALL supply a `ReturnPlan` that contains the item number, the evidence comment, the repository name, and the status record marks.

#### Scenario: Stage returns an unbuildable premise item through apply_return
- **WHEN** the stage job encounters a false premise or an item that cannot be built as written
- **THEN** the stage job calls `apply_return` with a `ReturnPlan` that contains the probe evidence comment and the edit next-step mark

#### Scenario: Stage returns an item blocked by open plans through apply_return
- **WHEN** the stage job finds that an item depends on missing paths from open plans
- **THEN** the stage job calls `apply_return` with a `ReturnPlan` that contains the blocked comment and the blocker marks

#### Scenario: Stage returns an item at the plan defect limit through apply_return
- **WHEN** an item reaches the plan defect limit
- **THEN** the stage job calls `apply_return` with a `ReturnPlan` that contains the defect problems comment and the failure marks
