# Spec Delta

## MODIFIED Requirements

### Requirement: The job commits the documentation and the archive, and pushes
After the last group the job SHALL run `uv run devops docs generate --sync-readme` and commit its changes, then `uv run devops openspec archive <change>` and commit its changes, then rebase, run the scoped checks, then push. The job SHALL run each of these outside the agent shell.

#### Scenario: Two groups
- **WHEN** a Staged low-effort P1 bug has a change with two unticked groups, and both steps pass
- **THEN** the branch holds the commit of the stage job, one commit for each group, one commit for the documentation and one commit for the archive, in that order, and `origin` holds the same branch

## ADDED Requirements

### Requirement: The job installs the hook environments before the first step
Before the first step of an item, the job SHALL run `pre-commit install-hooks` in the worktree, outside the agent shell, with `PRE_COMMIT_HOME` under the data directory. A failure SHALL stop the item at the step `hooks` with the output as the reason, before any model request. A repository with no `.pre-commit-config.yaml` SHALL get no install and no `pre-push` check.

#### Scenario: The install fails
- **WHEN** `pre-commit install-hooks` exits 1
- **THEN** no step runs, no model request is made, the item is stopped with the step `hooks`, and the reason holds the output

### Requirement: The job runs the scoped checks before it pushes
After the final rebase and before the push, the job SHALL run, in this order, the `pre-push` stage of the hooks over the commits past the default branch, `devops ci --check --only constructs,docs,openspec`, and `devops ci test --no-fallback` with the changed Python files of `src/` and `tests/`. It SHALL run each outside the agent shell and without a GitHub token. It SHALL run no test command when no such file changed. The job SHALL push only a head that passed all of them.

#### Scenario: All checks pass
- **WHEN** an item changes `src/devops_cli/shout.py` and `tests/test_shout.py` and every scoped check exits 0
- **THEN** `devops ci test` ran with those two paths, the job pushed, and no fix step ran

#### Scenario: A change with no Python file
- **WHEN** the item changes only documents
- **THEN** the job runs no test command, and pushes after the other checks pass

#### Scenario: The pre-push stage runs
- **WHEN** the job runs the scoped checks
- **THEN** one call is `pre-commit run --hook-stage pre-push --from-ref origin/main --to-ref HEAD` in the worktree

### Requirement: A failed scoped check gets fix steps, and an exhausted budget stops the item
A failed scoped check SHALL start a fix step with the name and the log of the check. Then the job SHALL generate the documentation again, commit its changes, and run the scoped checks again. The job SHALL run at most `roadmap.implement.repair_rounds` fix steps for the scoped checks. When no round is left, or a fix step stops, the job SHALL stop the item at the step `scoped checks` and push nothing.

#### Scenario: An ast-grep violation is repaired before the push
- **WHEN** the scoped static check exits 1 with a `pytest.raises` that has no `match`, and the fix step of the stub model adds the `match`
- **THEN** the fix commit is on the branch, the checks run again and pass, and the first push holds the fix

#### Scenario: A check that no fix repairs
- **WHEN** the `pre-push` stage exits 1 after every fix step, and `repair_rounds` is 3
- **THEN** three fix steps ran, `origin` holds no push of this run for the item, the item is stopped with the step `scoped checks`, and the reason holds the output of the check

### Requirement: The comment on the pull request shows the repair rounds and the scoped checks
The comment of the job on the pull request SHALL show, for each step, the repair rounds that it used, and SHALL show one line for each run of a scoped check with its name, its result and its seconds.

#### Scenario: One repair round
- **WHEN** the step of group 1 used one repair round and the scoped checks passed
- **THEN** the line of group 1 shows 1 repair round, and a line for each scoped check shows `passed` and its seconds
