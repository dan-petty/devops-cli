## ADDED Requirements

### Requirement: A failed stage item records its failure class and step
When the stage job records a failure in the job record of an item, it SHALL write `stage.failed_class`, the failure class of the exception, and `stage.failed_step`, the step, in the same write as `stage.failed_at` and `stage.failed_error`. The step SHALL be `plan` for a failure of the plan and `apply` for a failure of a write. A staged item and an item stopped on the budget SHALL clear both keys with `stage.failed_at` and `stage.failed_error`.

#### Scenario: A provider error in the plan
- **WHEN** the model call of an item fails with a provider error
- **THEN** the job record holds the class `provider` and the step `plan`

#### Scenario: A refused plan
- **WHEN** the plan of an item breaks a rule of the stage job
- **THEN** the job record holds the class `plan_defect` and the step `plan`

#### Scenario: A failed write
- **WHEN** a write of an item fails
- **THEN** the job record holds the step `apply`

#### Scenario: An item that changed during the job
- **WHEN** a write fails with the error that the item changed
- **THEN** the job record holds the class `head_moved`

#### Scenario: A staged item
- **WHEN** a round stages an item whose record holds a failure
- **THEN** the record holds no `stage.failed_at`, `stage.failed_error`, `stage.failed_class` or `stage.failed_step`

#### Scenario: The request count
- **WHEN** a round records a failure
- **THEN** the round writes the four keys with the one write that it made before
