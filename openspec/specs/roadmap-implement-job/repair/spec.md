# roadmap-implement-job/repair Specification

## Purpose
The repair of a failed check: the hook environments and the scoped checks before a push, the fix steps of a failed check, and the comment that shows the repair rounds.

## Requirements

### Requirement: A failed check of the pull request gets bounded fix steps
When the settled checks of the pull request hold a failed one, the job SHALL run a fix step with the log of the failed run, rebase, run the scoped checks, push, and watch again. It SHALL do so at most `roadmap.implement.repair_rounds` times, with a comment on the pull request for each round. A check that still fails after the last round, a check that does not settle within `CONST_ROADMAP_IMPLEMENT_MONITOR_TIMEOUT_SECONDS`, an unresolved review thread and a merge conflict SHALL stop the item.

#### Scenario: A check fails once
- **WHEN** the first watch shows a failed check, the fix step passes, and the second watch shows every check passed
- **THEN** the job pushes the fix commit, marks the pull request ready, and sets Status to In Review

#### Scenario: A check fails twice
- **WHEN** the check fails after the first and the second fix step, and passes after the third
- **THEN** two fix steps ran, the job marks the pull request ready, and the pull request holds one comment for each round

#### Scenario: A check fails in every round
- **WHEN** the check fails after each of the 3 fix steps, and `repair_rounds` is 3
- **THEN** the item is stopped with the step `checks`, the pull request stays a draft, and no fourth fix step runs

#### Scenario: No round
- **WHEN** `repair_rounds` is 0 and a check fails
- **THEN** the item is stopped with the step `checks` and no fix step runs

#### Scenario: The watch sees the old head
- **WHEN** the first read after a push still shows the previous head commit of the pull request
- **THEN** the job reads again, and judges only a status whose head is the pushed commit

### Requirement: The job installs the hook environments before the first step
Before the first step of an item, the job SHALL run `pre-commit install-hooks` in the worktree, outside the agent shell, with `PRE_COMMIT_HOME` under the data directory. A failure SHALL stop the item at the step `hooks` with the output as the reason, before any model request. A repository whose default branch holds no `.pre-commit-config.yaml` SHALL get no install and no `pre-push` check.

#### Scenario: The install fails
- **WHEN** `pre-commit install-hooks` exits 1
- **THEN** no step runs, no model request is made, the item is stopped with the step `hooks`, and the reason holds the output

### Requirement: The job runs the scoped checks before it pushes
After the final rebase and before the push, the job SHALL run, in this order, the `pre-push` stage of the hooks over the commits past the default branch, `devops ci --check --only constructs,docs,openspec`, and `devops ci test` with test modules. It SHALL run each outside the agent shell and without a GitHub token. The job SHALL push a finished item only after all of them pass, except for a checkpoint.

#### Scenario: All checks pass
- **WHEN** an item changes `src/devops_cli/shout.py`, a test module imports it, and every scoped check exits 0
- **THEN** `devops ci test` ran with the path of that test module, the job pushed, and no fix step ran

#### Scenario: A change with no Python file
- **WHEN** the item changes only documents
- **THEN** the job runs no test command, and pushes after the other checks pass

#### Scenario: The pre-push stage runs
- **WHEN** the job runs the scoped checks
- **THEN** one call is `pre-commit run --hook-stage pre-push --from-ref origin/main --to-ref HEAD` in the worktree

#### Scenario: A checkpoint comes before the scoped checks
- **WHEN** group 1 of two groups passes its step, and the job reaches the boundary of group 2
- **THEN** `origin` holds the commit of group 1 before any scoped check runs, and the final push still follows only after the scoped checks pass

### Requirement: The scoped tests check stays small
The test modules of the scoped tests check SHALL be those that the selector of `devops ci test` picks for the changed Python files of `src/` and `tests/`. The job SHALL run no test command when no test covers the change. It SHALL run only the changed test modules when the selection holds more than `CONST_ROADMAP_IMPLEMENT_SCOPED_TEST_MODULES` modules. The comment on the pull request SHALL say so.

#### Scenario: A change that no test covers
- **WHEN** the item changes a source that no test module imports
- **THEN** the job runs no test command, the check is not a failure, and the comment says that no test covers the changed files

#### Scenario: A shared module
- **WHEN** the item changes a module that more than the limit of test modules import, and one test module
- **THEN** `devops ci test` ran with the changed test module only, and the comment says that the others are left to the required checks of CI

### Requirement: Every hook run reads the configuration of the default branch
Every `pre-commit` call of the job SHALL name, with `--config`, a copy of the `.pre-commit-config.yaml` of the default branch, never the file of the checkout. The job SHALL run no hook when the default branch holds none. The copy SHALL leave out a hook whose program the runner image does not hold and that is not on PATH, because no agent can repair a missing program; the checks of the pull request run that hook.

#### Scenario: The agent edits the hook configuration
- **WHEN** the agent writes `repos: []` to `.pre-commit-config.yaml`
- **THEN** every `pre-commit` call names the copy of the configuration of the default branch with `--config`

#### Scenario: A hook whose program is missing
- **WHEN** the default branch configuration holds the hook `devops-ci-workflows-pre-push` and `actionlint` is not on PATH
- **THEN** the copy holds every other hook and not that one

### Requirement: A failed scoped check gets fix steps, and a stop in the phase keeps the work
A failed scoped check SHALL start a fix step with the name and the log of the check. Then the job SHALL generate the documentation again, commit its changes, and run the scoped checks again, at most `roadmap.implement.repair_rounds` times. When no round is left, a fix step stops, an error occurs or a command runs out of time, the job SHALL stop the item and push the commits that passed, as at any other stop. The pull request SHALL stay a draft.

#### Scenario: An ast-grep violation is repaired before the push
- **WHEN** the scoped static check exits 1 with a `pytest.raises` that has no `match`, and the fix step of the stub model adds the `match`
- **THEN** the fix commit is on the branch, the checks run again and pass, and the first push holds the fix

#### Scenario: An error in the scoped checks
- **WHEN** git fails while the job reads the hook configuration after the archive
- **THEN** the item is stopped with the step `scoped checks`, `origin` holds the commits of both groups, and the stop comment names the branch and the last commit

#### Scenario: A hook stage runs out of time in a fix step
- **WHEN** the `pre-commit` stage of a fix step runs out of time
- **THEN** the item is stopped with the step `fix`, the reason says that the command ran out of time, and `origin` holds the commits of both groups

#### Scenario: A check that no fix repairs
- **WHEN** two groups pass, the `pre-push` stage exits 1 after every fix step, and `repair_rounds` is 3
- **THEN** three fix steps ran, `origin` holds the commits of both groups, the item is stopped with the step `scoped checks`, the reason holds the output of the check, the comment names the branch and its last commit, and the job sent no ready request

#### Scenario: A fix step stops
- **WHEN** the fix step of a failed scoped check stops
- **THEN** `origin` holds the commits of both groups, the item is Blocked at the step `fix`, and the comment names the kept work and the action left

#### Scenario: The next Job resumes from the kept work
- **WHEN** a person comments `implement: retry` after a stop in the scoped checks, and the next Job takes the item
- **THEN** the next Job runs no step for a group, runs the scoped checks, and its push holds the commits of the first Job

### Requirement: The comment on the pull request shows the repair rounds and the scoped checks
The comment of the job on the pull request SHALL show a table with one row for each step: the step, its status, its attempts (the first turn and the repair rounds), its tokens in and out and its last failing command. It SHALL show one line for each run of a scoped check with its name, its result and its seconds.

#### Scenario: One repair round
- **WHEN** the step of group 1 used one repair round and the scoped checks passed
- **THEN** the row of group 1 shows 2 attempts, and a line for each scoped check shows `passed` and its seconds

### Requirement: A stop names the failed check and the end of its log
A stop of a fix step, and a stop of the scoped checks, SHALL name the failed check and hold the end of its log, at most `CONST_ROADMAP_IMPLEMENT_CHECK_LOG_CHARS` characters, with secrets masked. The stop comment and the job record (`implement.check`, `implement.check_log`) SHALL hold both. The next Job SHALL remove `implement.check_log` in its first record write. The comment table SHALL show the check name as the last failing command when no command failed.

#### Scenario: A fix step that stops
- **WHEN** the check `Tests & Coverage` of the pull request fails with a log that holds a token, and the fix step changes no file
- **THEN** the comment names `Tests & Coverage`, holds the end of the log with the token masked, the row `fix` of the table shows the check name, and `implement.check` and `implement.check_log` hold the same

#### Scenario: A scoped check that still fails
- **WHEN** the scoped check `pre-push` fails after the last fix round
- **THEN** the comment and the record hold the name `pre-push` and the end of its log

#### Scenario: A retry
- **WHEN** a trusted person comments `implement: retry` and the job takes the item
- **THEN** `implement.check` and `implement.check_log` are removed

#### Scenario: A clear rule keeps the log
- **WHEN** a clear rule of the Service removes the stop of an item
- **THEN** `implement.check` is removed and `implement.check_log` stays

### Requirement: The comment puts the failed check first and labels the claim
The stop comment SHALL start, after the step, with the failed check. The failed check is the check that the stop names, or else the last command of the step that did not exit 0. The class lines SHALL follow it, and the reason SHALL follow them. The comment SHALL name the last message of the agent as a claim that no check verified.

#### Scenario: The order of the comment
- **WHEN** a stop has a failed check, a reason and a last message
- **THEN** the failed check comes before the class lines, the class lines come before the reason, and the last message follows a label that says that no check verified it

### Requirement: A failed check outside the repair scope gets no fix turn
The job SHALL stop the item as Blocked with no model request when the log of a failed check of the pull request names no path of the repair scope. The scope SHALL hold each path that the plan names in the code spans of its groups, and each file of the change folder. The stop reason SHALL name the check and the scope.

#### Scenario: A workflow check outside the plan fails after the push
- **WHEN** the check `Deploy Preview` fails and its log names no path of the repair scope
- **THEN** the job runs no fix step, the item is Blocked, and the reason names `Deploy Preview` and the paths of the scope

#### Scenario: A check on a path of the plan fails
- **WHEN** the check `Static Analysis` fails and its log names `src/app.py`, which the plan names
- **THEN** the job runs a fix step, at most `repair_rounds` times
