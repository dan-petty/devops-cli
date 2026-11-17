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
After the final rebase and before the push, the job SHALL run, in this order, the `pre-push` stage of the hooks over the commits past the default branch, `devops ci --check --only constructs,docs,openspec`, `devops ci test` with test modules, and the strength check of the new tests. It SHALL run each outside the agent shell and without a GitHub token. The job SHALL push a finished item only after all of them pass, except for a checkpoint.

#### Scenario: All checks pass
- **WHEN** an item changes `src/devops_cli/shout.py`, a test module imports it, and every scoped check exits 0
- **THEN** `devops ci test` ran with the path of that test module, the job pushed, and no repair step ran

#### Scenario: A change with no Python file
- **WHEN** the item changes only documents
- **THEN** the job runs no test command, and pushes after the other checks pass

#### Scenario: The pre-push stage runs
- **WHEN** the job runs the scoped checks
- **THEN** one call is `pre-commit run --hook-stage pre-push --from-ref origin/main --to-ref HEAD` in the worktree

#### Scenario: A checkpoint comes before the scoped checks
- **WHEN** group 1 of two groups passes its step, and the job reaches the boundary of group 2
- **THEN** `origin` holds the commit of group 1 before any scoped check runs, and the final push still follows only after the scoped checks pass

#### Scenario: The strength check follows the tests check
- **WHEN** the tests check passes
- **THEN** the strength check runs on the changed files, and the push follows only after it passes or reaches its bound

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

### Requirement: The job checks the strength of the new tests
The implement job SHALL run a strength check after the scoped tests check. It SHALL report a new test file whose test functions hold no assertion, a mutant that no test kills, and a changed line that the scoped test modules do not cover. It SHALL measure that coverage in a run of the scoped test modules with coverage turned on. It SHALL give each finding to a repair step of the scoped-check repair loop.

#### Scenario: A test file that asserts nothing
- **WHEN** a new test file holds a test function with no assert statement and no call of pytest.raises or pytest.warns
- **THEN** the strength check reports the file and the line of the function, and the scoped check named `strength` fails

#### Scenario: A surviving mutant
- **WHEN** the mutation run reports one surviving mutant
- **THEN** the strength check reports the file, the line and the name of the mutant, and the scoped check named `strength` fails

#### Scenario: An uncovered new line
- **WHEN** the coverage run of the scoped test modules executes no changed line of a source file
- **THEN** the strength check reports the file and the line of the uncovered line, and the scoped check named `strength` fails

### Requirement: The strength check is bounded
The strength check SHALL stop its mutation run at `roadmap.implement.command_timeout_seconds`. It SHALL run the mutation run on the changed source files of at most `CONST_ROADMAP_IMPLEMENT_SCOPED_TEST_MODULES` files. A run that reaches either bound SHALL NOT fail the check, and the report SHALL name the bound and each file that the run did not test.

#### Scenario: The command timeout is reached
- **WHEN** the mutation run reaches the command timeout of the step
- **THEN** the run stops, and the report names the bound and the mutants that survived before the stop

#### Scenario: More changed files than the bound
- **WHEN** a change touches more source files than `CONST_ROADMAP_IMPLEMENT_SCOPED_TEST_MODULES`
- **THEN** the run tests the files up to the bound, and the report names each file that the run did not test

### Requirement: The strength check skips the files of a group of kind other
The strength check SHALL leave out the changed files that a task group of kind `other` names. It SHALL run no mutation check and no coverage check on those files, and the report SHALL name the group and the reason.

#### Scenario: A group of kind other
- **WHEN** a task group has the line `Kind: other.` and names a changed file
- **THEN** the strength check leaves that file out of the assertion scan, the mutation run and the coverage delta, and the report names the group

#### Scenario: Every changed file belongs to a group of kind other
- **WHEN** every changed file belongs to a task group of kind `other`
- **THEN** the strength check runs no mutation check and no coverage check, and the comment states the skip reason

### Requirement: The comment shows the strength report
The comment of the job on the pull request SHALL show the strength report: each surviving mutant with its file, line and name, each uncovered changed line with its file and line, the bound that a mutation run reached, and the reason when the check skips the files of a group of kind other.

#### Scenario: A surviving mutant in the comment
- **WHEN** the strength check reports one surviving mutant
- **THEN** the comment lists its file, its line and its name

#### Scenario: An uncovered changed line in the comment
- **WHEN** the strength check reports one uncovered changed line
- **THEN** the comment lists its file and its line number

#### Scenario: A skipped group in the comment
- **WHEN** the strength check skips the files of a task group of kind other
- **THEN** the comment states the group number and the reason of the skip

### Requirement: The mutation run takes its test selection from the mutmut table
While `mutmut run` runs, the mutation run of the strength check SHALL give the scoped test modules to mutmut in `pytest_add_cli_args_test_selection` of `[tool.mutmut]` in the `pyproject.toml` of the checkout, after the entries of that table. The command SHALL set no environment key that `build_subprocess_env` refuses.

#### Scenario: Two scoped test modules
- **WHEN** the table holds `--ignore=tests/test_docs.py` and the mutation run gets `tests/test_sample.py` and `tests/test_other.py`
- **THEN** while `mutmut run` runs, the selection is `--ignore=tests/test_docs.py`, `tests/test_sample.py` and `tests/test_other.py`

#### Scenario: The environment of the run
- **WHEN** the environment that the mutation run gives to `run_subprocess` goes to `build_subprocess_env`
- **THEN** no `SecurityError` occurs, and the child environment holds no `PYTEST_ADDOPTS`

### Requirement: The mutation run leaves the mutmut table as it found it
After the mutation run, the `pyproject.toml` of the checkout SHALL hold the bytes that it held before the run, also when the command raises or reaches the timeout. A checkout with no `pyproject.toml` SHALL have none after the run. With no scoped test module, the run SHALL leave the file as it is.

#### Scenario: A finished run
- **WHEN** the mutation run with two scoped test modules ends
- **THEN** the file holds its original text

#### Scenario: A run that reaches the timeout in a checkout with no pyproject.toml
- **WHEN** the checkout has no `pyproject.toml` and `mutmut run` reaches the timeout
- **THEN** the selection during the run is the scoped test module, and the checkout has no `pyproject.toml` after the run

### Requirement: The mutation run mutates only the files of its targets and removes its tree
While `mutmut run` and `mutmut results` run, the mutation run of the strength check SHALL set `only_mutate` of `[tool.mutmut]` in the `pyproject.toml` of the checkout to the files of its targets, each file once. After it reads the results, it SHALL remove the directory `mutants/` of the checkout, also when a command raises or reaches the timeout.

#### Scenario: Three targets in two files
- **WHEN** the mutation run gets two targets in `src/sample.py` and one target in `src/other.py`
- **THEN** `only_mutate` is `src/sample.py` and `src/other.py` while `mutmut run` and `mutmut results` run, and the checkout has no `mutants/` after the run

#### Scenario: A run that reaches the timeout
- **WHEN** `mutmut run` reaches the timeout after it wrote `mutants/`
- **THEN** the run reads the results, and the checkout has no `mutants/` after the run

### Requirement: The coverage report of the strength check takes no floor of its own
The coverage run of the strength check SHALL write its report with `coverage xml --fail-under=0`, so that the `fail_under` of `[tool.coverage.report]`, the floor of the whole suite, does not fail a scoped run. diff-cover with `--fail-under 90` SHALL stay the bound of the changed lines.

#### Scenario: A scoped run under the floor of the whole suite
- **WHEN** the scoped test modules cover 17% of `src`, the file sets `fail_under = 85`, and diff-cover finds every changed line covered
- **THEN** the coverage delta passes and holds no log

### Requirement: A change with no source file runs only the assertion scan
When no active changed file of the strength check is a Python file under `src/`, the strength check SHALL run the assertion scan only, SHALL start no mutation run and no coverage run, and SHALL add the note that names the reason to its report.

#### Scenario: A change of a test, a manifest and a prompt
- **WHEN** the changed files are `tests/test_sample.py`, `k8s/runner.yaml` and `src/devops_cli/ai/tasks/step.md`, and the new test asserts
- **THEN** the strength check passes, no `pytest`, `coverage` or `mutmut` command starts, and the report holds the note
