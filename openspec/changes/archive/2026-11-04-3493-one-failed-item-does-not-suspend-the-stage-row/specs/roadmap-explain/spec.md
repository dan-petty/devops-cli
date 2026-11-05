## ADDED Requirements

### Requirement: The command reports an item that the stage job holds for a retry
For the stage job, `devops roadmap explain <issue>` SHALL read `stage.failed_at` and `stage.failed_error` in the job record of the item on GitHub. When the failure is younger than `roadmap.stage.retry_hours` hours, the stage job SHALL be `no`, and the reason SHALL name the error class and the time after which the job takes the item again.

#### Scenario: A held item
- **WHEN** the job record of a Ready item holds a failure of 5 minutes ago with the class `AIClientError`
- **THEN** the stage job is `no` and the reason names `AIClientError` and the time of the retry
