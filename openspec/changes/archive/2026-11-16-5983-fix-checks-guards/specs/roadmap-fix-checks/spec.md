## ADDED Requirements

### Requirement: The step leaves an item to its live implement Job
When the record of the item names an implement Job with no recorded state (`implement.job` set and `implement.job_state` empty), the step SHALL return `skipped` with no checkout, no comment and no mark. A Job with a recorded state has ended and SHALL NOT stop the step.

#### Scenario: An item that a live implement Job holds is skipped
- **WHEN** the step runs with `--confirm` on a bot pull request whose item records `implement.job` and no `implement.job_state`
- **THEN** the step returns `skipped` with a reason that names the Job, and makes no checkout, no comment and no mark

#### Scenario: An item whose implement Job ended is judged
- **WHEN** the step runs on a bot pull request whose item records `implement.job` and `implement.job_state`
- **THEN** the step judges the failed check

### Requirement: The step does not repeat a round that ended with no repair
When `fix_checks.key` equals `<head>:<check>` of the first failed check and `fix_checks.result` is `failed`, `stopped` or `wait`, the step SHALL return `skipped` before it reads the log, with no model request, no comment and no new mark. A new head or another failed check SHALL start a round.

#### Scenario: The same head and check get no second round
- **WHEN** the step runs with `--confirm` on a head and check whose last round ended `failed`, `stopped` or `wait`
- **THEN** the step returns `skipped`, makes no checkout and no model request, posts no comment, and leaves the record as it is

#### Scenario: A new head or a new failed check starts a round
- **WHEN** the record holds a failed round of another head, or of another check on the same head
- **THEN** the step runs the round on the head and check of now

## MODIFIED Requirements

### Requirement: The step admits only bot pull requests and enforces bounds
The step `fix-checks` SHALL judge only open bot pull requests. It SHALL stop on pull requests that have `owner/*` labels. When an expected head is given, the step SHALL skip when the remote head differs. It SHALL enforce a soft cap of 3 rounds (extendable while error count decreases), a hard cap of 5 rounds, and at most 3 distinct heads per pull request. The cap of heads SHALL apply only to a head with a failed check.

#### Scenario: A pull request with an owner label stops
- **WHEN** `fix-checks` runs on a pull request with an `owner/human` or `owner/agent` label
- **THEN** the step stops and makes no changes

#### Scenario: A moved head returns skipped
- **WHEN** the head of the pull request differs from the expected head
- **THEN** the step returns skipped

#### Scenario: Caps enforce round limits
- **WHEN** a pull request reaches 5 rounds or reaches the soft cap without error reduction
- **THEN** the step halts further attempts

#### Scenario: Head cap stops after 3 heads
- **WHEN** a pull request already has 3 distinct heads recorded and a new head arrives with a failed check
- **THEN** the step halts further attempts

#### Scenario: A draft whose checks pass after the third repair is marked ready
- **WHEN** the step runs with `--confirm` on the head that its third repair pushed, every check passes, and `draft_readiness` answers ready
- **THEN** the step marks the draft ready and returns `ready`

### Requirement: Tier 1 resolves deterministic check failures with zero model calls
When a check failure is classified as `lint`, the step SHALL run `ruff check --fix` and `ruff format` on the changed files. When the log shows a docs failure, the step SHALL run `devops docs generate`, and when it shows a lockfile failure, `uv lock`, whatever the class of the check. The step SHALL run the check again locally, and when it passes, push the repair with zero model requests.

#### Scenario: Tier 1 fixes a lint failure with 0 model requests
- **WHEN** a pull request check fails on code formatting or lint errors
- **THEN** the step runs the lint fixers and pushes the repair with 0 model requests

#### Scenario: Tier 1 fixes a docs failure
- **WHEN** a pull request check fails because documentation is out of sync
- **THEN** the step regenerates the documentation and pushes the repair

#### Scenario: Tier 1 fixes a lockfile failure
- **WHEN** a pull request check fails because uv.lock is not updated
- **THEN** the step updates the lockfile and pushes the repair

#### Scenario: A lockfile failure in a test check gets uv lock
- **WHEN** `uv sync --locked` fails in the check `Tests & Coverage`, whose class is test
- **THEN** tier 1 runs `uv lock` and `uv lock --check`, commits `uv.lock`, and makes no model request

### Requirement: CI infrastructure failures post a comment and wait
When the failure is classified as `ci_infra` and its log shows no docs or lockfile failure, the step SHALL post one comment explaining the infrastructure failure and return status `wait`.

#### Scenario: A CI infrastructure failure waits
- **WHEN** a check fails due to CI infrastructure issues
- **THEN** the step posts a comment, records result wait, and stops

#### Scenario: A lockfile failure in a check of the class ci_infra goes to tier 1
- **WHEN** a stale `uv.lock` fails a check whose name the class reads as infrastructure
- **THEN** the step posts no comment and runs tier 1

### Requirement: The command repairs a failed check in a runner Job
With `--confirm`, `devops roadmap step fix-checks` SHALL refuse to run outside a runner Job. In a runner Job it SHALL give the step a worktree on the head branch of the pull request, the tier 1 fixers, and the model fix on the task `ai.tasks.fix_checks`. The step SHALL push the commit of a fixer to the head branch with a lease on the judged head, and SHALL return `repaired` with the new head.

#### Scenario: A failed check whose log names a file of the plan ends repaired
- **WHEN** the command runs with `--confirm` on a bot pull request whose `Static Analysis` check failed with a log that names a file of the plan, and the model fix commits a change
- **THEN** the step returns `repaired`, and the head branch on `origin` has one new commit

#### Scenario: The command refuses to repair outside a runner Job
- **WHEN** the command runs with `--confirm` in a process that is not a runner Job
- **THEN** the command exits 1 and reads no pull request

#### Scenario: A push whose lease breaks is refused
- **WHEN** another writer moves the head branch on `origin` after the judgment and before the push
- **THEN** the push fails, the commit of the other writer stays, the step records no repair, and the worktree goes

#### Scenario: The checkout refuses another branch or another head
- **WHEN** the branch of the item is not the head branch of the pull request, or its tip is not the judged head
- **THEN** the checkout raises an error before any fixer runs, and its worktree and local branch go
