## MODIFIED Requirements

### Requirement: The command reports an item that the stage job holds for a retry
For the stage job, `devops roadmap explain <issue>` SHALL read `stage.failed_at`, `stage.failed_error` and `stage.failed_class` in the job record of the item on GitHub. When the failure is younger than the wait of its class (`RETRY_AFTER`, and `ci_infra` for a record with no class), the stage job SHALL be `no`, and the reason SHALL name the error class and the time after which the job takes the item again.

#### Scenario: A held item
- **WHEN** the job record of a Ready item holds a failure of 5 minutes ago with the error `RoadmapStageError` and the class `plan_defect`
- **THEN** the stage job is `no` and the reason names `RoadmapStageError` and the time 1 hour after the failure

#### Scenario: A held item with no class
- **WHEN** the job record of a Ready item holds a failure of 5 minutes ago with the error `AIClientError` and no class
- **THEN** the stage job is `no` and the reason names `AIClientError` and the time 1 hour after the failure
