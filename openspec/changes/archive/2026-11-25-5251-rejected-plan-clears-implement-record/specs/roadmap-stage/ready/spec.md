## ADDED Requirements

### Requirement: Stage ready reads only a live implement Job
`stage_ready` SHALL use `job_holds` to decide whether an active implement runner Job holds an item, so an ended Job whose `implement.job_state` is recorded does not block marking a new plan draft ready.

#### Scenario: Finished Job does not hide a new draft
- **WHEN** an item holds `implement.job` with a finished `implement.job_state` and a green staged draft pull request
- **THEN** `mark_stage_ready` does not skip the draft and marks it ready
