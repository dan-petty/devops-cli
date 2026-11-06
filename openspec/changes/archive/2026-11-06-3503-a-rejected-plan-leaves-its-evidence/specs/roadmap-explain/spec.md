## ADDED Requirements

### Requirement: Explain names the plan pull request of a rejected item
`devops roadmap explain <issue>` SHALL print, for the stage job, the reason that the job gives for an item that holds a `stage.rejected` record, and the reason SHALL name the plan pull request that a person closed.

#### Scenario: A rejected item that is Ready again
- **WHEN** a Ready item holds a `stage.rejected` record for pull request 7, its text hashes as recorded and no named file changed
- **THEN** the stage job is `no` and the reason names pull request 7 and says what ends the leave-out
