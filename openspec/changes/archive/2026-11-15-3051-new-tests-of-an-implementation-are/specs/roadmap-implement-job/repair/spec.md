## ADDED Requirements

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

## MODIFIED Requirements

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
