## ADDED Requirements

### Requirement: A rejected plan clears the implement run keys
When `stage` records a closed, unmerged plan pull request as rejected, it SHALL clear the implement run keys while preserving non-run history (`implement.continuations`, `implement.digest_clears`, `implement.spend`).

#### Scenario: Rejected plan clears implement run keys
- **WHEN** `stage` records a rejected plan for an item holding `implement.job`, `implement.job_state`, `implement.stopped`, `implement.failure`, `implement.branch`, `implement.pr`, and `implement.continuations`
- **THEN** the implement run keys are cleared while `implement.continuations` and `stage.rejected` remain, `recorded_branch` returns `None`, and `sync_statuses` derives `Ready` after the item becomes `Ready`
