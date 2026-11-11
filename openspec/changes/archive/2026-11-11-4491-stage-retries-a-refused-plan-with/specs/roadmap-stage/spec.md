## ADDED Requirements

### Requirement: Refused plans count on their body
When the stage job records a `plan_defect` failure, it SHALL write in the same write `stage.plan_defects`, the count of such failures on the body, and `stage.plan_defects_body`, the hash of the body without the block of the alternatives job. A body that hashes differently SHALL start the count at 1. A failure of another class SHALL keep both keys and its own `RETRY_AFTER` wait.

#### Scenario: A second refused plan on the same body
- **WHEN** the job records the second `plan_defect` failure of an item whose body did not change
- **THEN** the job record of the item holds `stage.plan_defects` 2, and the item stays Ready

#### Scenario: An edited body starts a new count
- **WHEN** an item has 2 `plan_defect` failures, a person edits its body, and the job records a `plan_defect` failure
- **THEN** the job record holds `stage.plan_defects` 1, and the item stays Ready with no comment of the job

#### Scenario: A provider failure does not count
- **WHEN** an item has 2 `plan_defect` failures and the job records a `provider` failure
- **THEN** the job record holds `stage.plan_defects` 2 and `stage.failed_class` `provider`

### Requirement: The limit of refused plans returns the item to New
The `plan_defect` failure that brings the count to `CONST_ROADMAP_STAGE_PLAN_DEFECT_LIMIT` (3) SHALL return the item to New in the same round. The job SHALL post one comment that lists in sequence, one line each and with no handle that pings, the problems of the refused replies of the last plan and then the reason of the failure, unless the checks refused the last reply. It SHALL then set New with the failure keys and clear both count keys.

#### Scenario: The third refused plan
- **WHEN** an item has 2 `plan_defect` failures on its body and a round of the Service refuses its plan again
- **THEN** the item is New, one comment of the stage job lists the problems of the refused replies, and the job record holds no `stage.plan_defects`

#### Scenario: A failure with no refused reply
- **WHEN** the failure at the limit holds no problem of a refused reply
- **THEN** the comment lists the reason of the failure

#### Scenario: A plan run that stops after a refused reply
- **WHEN** the checks refuse the first reply of the last plan and the second plan run stops
- **THEN** the comment lists the problem of the refused reply and then the reason of the stop

#### Scenario: A problem that names a handle
- **WHEN** a problem at the limit holds a handle and a line break
- **THEN** the comment shows the problem on one line with the handle in a code span

### Requirement: A staged item clears the count of refused plans
A run that stages an item SHALL clear `stage.plan_defects` and `stage.plan_defects_body` in the write of its stage record.

#### Scenario: A staged item after a refused plan
- **WHEN** a round stages an item whose job record holds a count of refused plans
- **THEN** the job record of the item holds neither count key
