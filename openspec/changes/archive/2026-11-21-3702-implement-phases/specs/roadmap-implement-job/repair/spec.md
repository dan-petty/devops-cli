## ADDED Requirements

### Requirement: The agent phase runs the scoped checks before publish pushes
After the archive and before `publish`, the agent phase SHALL run, in this order, the `pre-push` stage of the hooks over the commits past the default branch, `devops ci --check --only constructs,docs,openspec`, `devops ci test` with test modules, and the strength check of the new tests. It SHALL run each outside the agent shell and without a GitHub token. `publish` SHALL push a finished item only after all of them pass.

#### Scenario: All checks pass
- **WHEN** an item changes `src/devops_cli/shout.py`, a test module imports it, and every scoped check exits 0
- **THEN** `devops ci test` ran with the path of that test module, the job pushed, and no repair step ran

#### Scenario: A change with no Python file
- **WHEN** the item changes only documents
- **THEN** the job runs no test command, and pushes after the other checks pass

#### Scenario: The pre-push stage runs
- **WHEN** the job runs the scoped checks
- **THEN** one call is `pre-commit run --hook-stage pre-push --from-ref origin/main --to-ref HEAD` in the clone

#### Scenario: No push before the scoped checks
- **WHEN** group 1 of two groups passes its step
- **THEN** `origin` holds no new commit before the scoped checks pass and `publish` runs

#### Scenario: The strength check follows the tests check
- **WHEN** the tests check passes
- **THEN** the strength check runs on the changed files, and the push follows only after it passes or reaches its bound

## REMOVED Requirements

### Requirement: The job runs the scoped checks before it pushes
**Reason**: No run makes a checkpoint, so no push comes before the scoped checks (#3702).
**Migration**: The requirement "The agent phase runs the scoped checks before publish pushes" replaces it.
