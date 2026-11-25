## ADDED Requirements

### Requirement: Fix-plan reads only a live implement Job
`fix_plan` SHALL use `job_holds` to decide whether an active implement runner Job holds an item, so an ended Job whose `implement.job_state` is recorded does not hide a plan draft labeled `verdict/fix-plan`.

#### Scenario: Finished Job does not hide a fix plan
- **WHEN** an item holds `implement.job` with a finished `implement.job_state` and a plan draft carrying `verdict/fix-plan`
- **THEN** `fix_plan` does not skip the draft for a runner Job
