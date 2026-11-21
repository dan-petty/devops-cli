## MODIFIED Requirements

### Requirement: The command repairs a failed check in a runner Job
With `--confirm`, `devops roadmap step fix-checks` SHALL refuse to run outside a runner Job. In a runner Job it SHALL give the step a plain clone on the head branch, the rebase onto main, the tier 1 fixers and the model fix of `ai.tasks.fix_checks`. The fix SHALL be one commit on the judged head, or, for a branch that the agent rebased, on the work, archive and later commits that replace the branch. `publish` SHALL push with a lease on the judged head, and return `repaired` with the new head.

#### Scenario: A failed check whose log names a file of the plan ends repaired
- **WHEN** the command runs with `--confirm` on a bot pull request whose `Static Analysis` check failed with a log that names a file of the plan, and the model fix commits a change
- **THEN** the step returns `repaired`, and the head branch on `origin` has one new commit

#### Scenario: The command refuses to repair outside a runner Job
- **WHEN** the command runs with `--confirm` in a process that is not a runner Job
- **THEN** the command exits 1 and reads no pull request

#### Scenario: A push whose lease breaks is refused
- **WHEN** another writer moves the head branch on `origin` after the judgment and before the push
- **THEN** the push fails, the commit of the other writer stays, and the step records no repair

#### Scenario: The checkout refuses another branch or another head
- **WHEN** `origin` holds no head branch of the pull request, or its tip is not the judged head
- **THEN** the checkout raises an error before any fixer runs

#### Scenario: A branch behind main is rebased and repaired
- **WHEN** main gets a new commit after the branch point, and the model fix commits a change
- **THEN** the step returns `repaired`, the new head holds the tip of main and not the judged head, and two commits follow the tip of main: the work of the branch and the fix

#### Scenario: The archive stays its own commit
- **WHEN** the branch ends with the archive commit of the item, and main gets a new commit after the branch point
- **THEN** three commits follow the tip of main: the work of the branch, the archive commit and the fix

#### Scenario: A rebase conflict that no rule settles
- **WHEN** main changes a source file that the branch also changes
- **THEN** the step returns `stopped` with a reason that starts with `Conflict: ` and names the file, sends no model request and pushes nothing

#### Scenario: A lease that moved after a rebase
- **WHEN** another writer moves the head branch after the rebase and before the push, and GitHub then gives the moved head
- **THEN** the step returns `skipped` with the reason `Head has moved: the lease refused the push`, and the commit of the other writer stays

## REMOVED Requirements

### Requirement: The repair scope takes the failed files that the change causes
**Reason**: The agent phase rebases a branch that is behind main before the scope check (#6639), so no failed file is main skew, and the main-skew stop goes.
**Migration**: The requirement "The repair scope takes the failed files that the rebased change causes" holds the same rules with no main-skew stop.

## ADDED Requirements

### Requirement: The repair scope takes the failed files that the rebased change causes
After the rebase, a failed file outside the plan SHALL be in the repair scope when the branch changes it, when it uses a function, class or method whose definition the branch changes, when it is a test that imports a module that the branch changes, or when it is a snapshot test whose snapshot differs while the branch changes a source module.

#### Scenario: A caller of a changed function outside the plan is repaired
- **WHEN** the plan adds the keyword-only argument `in_runner` to `_run_pr_review_workflow`, and the log names `FAILED tests/git/test_review_worktree_regression.py::test_run_pr_review_workflow_partial_context - TypeError: _run_pr_review_workflow() missing 1 required keyword-only argument: 'in_runner'`, a file that the plan does not list and that calls the function
- **THEN** the step gives the file to `run_fix_step`, which may change it, and pushes the repair

#### Scenario: A log that names no file of the checkout stops
- **WHEN** the log names no failed file that the checkout tracks, such as the end of an ignore of a scanner
- **THEN** the step stops with 0 model requests, and the reason says that the log names no path of the plan and no file that the change causes
