## RENAMED Requirements

- FROM: `### Requirement: A failed scoped check gets fix steps, and an exhausted budget stops the item`
- TO: `### Requirement: A failed scoped check gets fix steps, and a stop in the phase keeps the work`

## MODIFIED Requirements

### Requirement: The job leaves out an item whose plan fails the check
The implement selection SHALL run `check_proposal` on the plan of a Staged or Planned item before it returns a target, and it SHALL leave the item out with the first problem as its reason when the check returns problems. It SHALL run no plan check on a Staged item whose branch head holds the archived change of the issue and no active one, because the job archives a change only after the plan passed the check.

#### Scenario: A Staged item with a placeholder task
- **WHEN** The branch of a Staged item holds a plan with the placeholder task `1.1 x`.
- **THEN** `plan_implement` returns no target for the item and its reason holds the first problem.

#### Scenario: A Planned item with a placeholder task
- **WHEN** The default branch holds the plan of a Planned item with the placeholder task `1.1 x`.
- **THEN** `plan_implement` returns no target and makes no branch for the item.

#### Scenario: A plan that passes the check
- **WHEN** The plan of the item passes every `check_proposal` gate.
- **THEN** `plan_implement` returns the item as a target.

#### Scenario: A plan with two problems
- **WHEN** The plan returns two or more problems and the job leaves the item out.
- **THEN** The reason of the item holds the first problem and no later problem.

#### Scenario: A plan that the reader refuses
- **WHEN** The change folder of the item is missing or holds a file that the reader cannot parse.
- **THEN** `plan_implement` returns no target, makes no branch, and its reason names the read problem.

#### Scenario: A test path that no file holds
- **WHEN** The verification command of group 1 names a test path that the staged commit does not hold and that no group creates.
- **THEN** `plan_implement` returns no target for the item, and its reason names the path, so no run starts to amend the path.

#### Scenario: A branch whose change is archived
- **WHEN** The branch head of a Staged item holds `openspec/changes/archive/<date>-1-<slug>/` and no `openspec/changes/1-*/`, and a person comments `implement: retry` after a stop
- **THEN** `plan_implement` returns the item as a target

### Requirement: The job runs the scoped checks before it pushes
After the final rebase and before the push, the job SHALL run, in this order, the `pre-push` stage of the hooks over the commits past the default branch, `devops ci --check --only constructs,docs,openspec`, and `devops ci test` with test modules. It SHALL run each outside the agent shell and without a GitHub token. The job SHALL push a finished item only after all of them pass. When a stop ends the run in this phase, the job SHALL push the commits that passed, as at any other stop, and SHALL NOT mark the pull request ready.

#### Scenario: All checks pass
- **WHEN** an item changes `src/devops_cli/shout.py`, a test module imports it, and every scoped check exits 0
- **THEN** `devops ci test` ran with the path of that test module, the job pushed, and no fix step ran

#### Scenario: A change with no Python file
- **WHEN** the item changes only documents
- **THEN** the job runs no test command, and pushes after the other checks pass

#### Scenario: The pre-push stage runs
- **WHEN** the job runs the scoped checks
- **THEN** one call is `pre-commit run --hook-stage pre-push --from-ref origin/main --to-ref HEAD` in the worktree

### Requirement: A failed scoped check gets fix steps, and a stop in the phase keeps the work
A failed scoped check SHALL start a fix step with the name and the log of the check. Then the job SHALL generate the documentation again, commit its changes, and run the scoped checks again. The job SHALL run at most `roadmap.implement.repair_rounds` fix steps for the scoped checks. When no round is left, or a fix step stops, the job SHALL stop the item at the step `scoped checks` or `fix`. An error or a command that runs out of time there SHALL stop the item too. Each of these stops SHALL push the commits that passed to the branch of the item on `origin`, leave the pull request a draft, and name the branch and its last commit in the stop comment.

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
