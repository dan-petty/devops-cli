## ADDED Requirements

### Requirement: A rebase that does not start is no conflict
When git refuses to start a rebase of the implement job, as in a checkout that holds changes, the job SHALL run no `git rebase --abort`, its reason SHALL say that the rebase did not start, and the stop SHALL have the class `ci_infra`, not `conflict`. A new Job starts from a new worktree, so the default action `retry` applies.

#### Scenario: A checkout that holds a changed file at the start
- **WHEN** a tracked file of the checkout is changed when the job rebases at the start of the run
- **THEN** the item stops at the rebase with the class `ci_infra`, the comment says that the rebase did not start and names no abort, `implement.conflict` holds no file, and the job runs no `git rebase --abort`
