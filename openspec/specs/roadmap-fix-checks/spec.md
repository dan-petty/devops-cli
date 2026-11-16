# roadmap-fix-checks Specification

## Purpose
How the roadmap step `fix-checks` repairs failed checks on pull requests: bounds enforcement, tier 1 deterministic repair with zero model calls, tier 2 model repair, plan scope confinement, and runner Job integration.

## Requirements

### Requirement: The step admits only bot pull requests and enforces bounds
The step `fix-checks` SHALL judge only open bot pull requests. It SHALL stop on pull requests that have `owner/*` labels. When an expected head is given, the step SHALL skip when the remote head differs. It SHALL enforce a soft cap of 3 rounds (extendable while error count decreases), a hard cap of 5 rounds, and at most 3 distinct heads per pull request.

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
- **WHEN** a pull request already has 3 distinct heads recorded and a new head arrives
- **THEN** the step halts further attempts

### Requirement: Tier 1 resolves deterministic check failures with zero model calls
When a check failure is classified as `lint`, the step SHALL run `ruff check --fix` and `ruff format` on the changed files. When a check failure is documentation-related, the step SHALL run `devops docs generate`. When a check failure is lockfile-related, the step SHALL run `uv lock`. The step SHALL run the check again locally, and when it passes, push the repair with zero model requests.

#### Scenario: Tier 1 fixes a lint failure with 0 model requests
- **WHEN** a pull request check fails on code formatting or lint errors
- **THEN** the step runs the lint fixers and pushes the repair with 0 model requests

#### Scenario: Tier 1 fixes a docs failure
- **WHEN** a pull request check fails because documentation is out of sync
- **THEN** the step regenerates the documentation and pushes the repair

#### Scenario: Tier 1 fixes a lockfile failure
- **WHEN** a pull request check fails because uv.lock is not updated
- **THEN** the step updates the lockfile and pushes the repair

### Requirement: Tier 2 repairs failures within plan scope using a model
When Tier 1 does not resolve the failure, the step SHALL inspect the failed log against the repair scope of the item. When the log names no path within the repair scope, the step SHALL stop with zero model calls. When the log names a path in scope, the step SHALL invoke `run_fix_step`.

#### Scenario: A log outside the plan scope stops with 0 model requests
- **WHEN** the failed check log names only paths outside the plan scope
- **THEN** the step stops with 0 model requests

#### Scenario: A log within plan scope runs a fix step
- **WHEN** the failed check log names a path within the plan scope
- **THEN** the step invokes `run_fix_step`

### Requirement: CI infrastructure failures post a comment and wait
When the failure is classified as `ci_infra`, the step SHALL post one comment explaining the infrastructure failure and return status `wait`.

#### Scenario: A CI infrastructure failure waits
- **WHEN** a check fails due to CI infrastructure issues
- **THEN** the step posts a comment, records result wait, and stops

### Requirement: The dry run makes zero requests
`devops roadmap step fix-checks --dry-run` SHALL make zero requests and mutate no state.

#### Scenario: Dry run
- **WHEN** `devops roadmap step fix-checks --pull 42 --dry-run` runs
- **THEN** the command exits 0 and makes zero requests

### Requirement: The command repairs a failed check in a runner Job
With `--confirm`, `devops roadmap step fix-checks` SHALL refuse to run outside a runner Job. In a runner Job it SHALL give the step a worktree on the head branch of the pull request, the tier 1 fixers, and the model fix on the task `ai.tasks.fix_checks`. The step SHALL push the commit of a fixer to the head branch with a lease on the judged head, and SHALL return `repaired` with the new head.

#### Scenario: A failed check whose log names a file of the plan ends repaired
- **WHEN** the command runs with `--confirm` on a bot pull request whose `Static Analysis` check failed with a log that names a file of the plan, and the model fix commits a change
- **THEN** the step returns `repaired`, and the head branch on `origin` has one new commit

#### Scenario: The command refuses to repair outside a runner Job
- **WHEN** the command runs with `--confirm` in a process that is not a runner Job
- **THEN** the command exits 1 and reads no pull request

### Requirement: The step writes nothing without --confirm
Without `--confirm`, the step SHALL return `planned` with the action that it would take. It SHALL post no comment, write no mark, make no checkout, run no fixer and push nothing.

#### Scenario: A run without --confirm writes nothing
- **WHEN** the step runs without `--confirm` on a bot pull request with a failed check
- **THEN** the step returns `planned`, and GitHub, the store and the branch are unchanged

### Requirement: The model fix of one run has a cap of new tokens
The model fix of one `fix-checks` run SHALL stop before a model request when its new tokens (input that the provider did not read from its cache, and output) reach `roadmap.fix_checks.token_budget`. The default SHALL be 16,000,000. The stop SHALL name the setting, and the cap SHALL get no extension.

#### Scenario: A fix step at its cap stops and names the setting
- **WHEN** the new tokens of the step reach the cap
- **THEN** the step stops before the next request, and the reason names `roadmap.fix_checks.token_budget`

### Requirement: The step marks a repaired draft ready only by the readiness rule
When the step finds an implement draft that it repaired, with every check passing on the head, it SHALL ask `draft_readiness`. It SHALL mark the draft ready with the expected head only when the answer is ready, and SHALL return `ready`. Otherwise it SHALL leave the draft as it is.

#### Scenario: A repaired draft whose checks pass is marked ready
- **WHEN** the step runs with `--confirm` on a repaired implement draft whose checks pass and that `draft_readiness` calls ready
- **THEN** the step marks the draft ready with the expected head and returns `ready`
