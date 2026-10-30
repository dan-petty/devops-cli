# Spec Delta

## MODIFIED Requirements

### Requirement: A failed exit check stops the step and resets the checkout
The exit checks SHALL run in this order: the agent made no commit, no test that existed at the start is lost, each verification command passes, the static checks pass, and every task of the group is ticked. The step SHALL stop at the first check that fails, name it as the reason, make no commit, and reset the checkout. A failed static check, and a task left unticked after the first four checks, first get the extra turn of their own requirements.

#### Scenario: A verification command fails
- **WHEN** the model ends its run with the files written and the tasks ticked, and the verification command exits 1
- **THEN** the step reports stopped, the reason names the command and its exit status, the checkout holds no new commit, and the written files are gone

#### Scenario: A static check fails
- **WHEN** the verification command exits 0 and `ruff check` exits 1 on the changed file, in the first turn and in the extra turn
- **THEN** the step reports stopped with the reason that `ruff check` failed, makes no commit and resets the checkout

#### Scenario: A task stays unticked
- **WHEN** the model ends its run and leaves a task of the group unticked, the verification command and the static checks exit 0, and the extra turn leaves the task unticked
- **THEN** the step reports stopped, the reason names the unticked task, and the checkout is reset

#### Scenario: A task stays unticked and a verification command fails
- **WHEN** the model ends its run and leaves a task of the group unticked, and the verification command exits 1
- **THEN** the step reports stopped with the reason that names the command and its exit status, the model gets no extra turn, and the checkout is reset

#### Scenario: The model changes another group
- **WHEN** the model changes the text of a task of group 2 while it works on group 1
- **THEN** the step reports done, and the commit holds group 2 as it was

#### Scenario: A task that the agent removes
- **WHEN** the model removes a task of group 1 from the `tasks.md` and ticks the others
- **THEN** the step ticks no task of group 1, gives the extra turn, and stops with the reason that names the first unticked task when the turn changes nothing

#### Scenario: A task that the agent moves
- **WHEN** the model swaps the texts of two tasks of group 1 and ticks them
- **THEN** the step reports done, and the commit holds the tasks in their order from before the run, ticked

#### Scenario: A heading that the agent changes
- **WHEN** the model changes the heading of group 1
- **THEN** the step reports done, and the commit holds the heading from before the run

#### Scenario: A tasks file that is gone
- **WHEN** the model removes the `tasks.md` of the change
- **THEN** the step writes the file from before the run, gives the extra turn for the unticked tasks, and stops with the reason that names the first unticked task when the turn changes nothing

#### Scenario: A verification command outside the allowlist
- **WHEN** a Verification line of the group names `curl http://example.com`
- **THEN** the step reports stopped, the reason names `curl` as not allowed, the command does not run, and the checkout is reset

#### Scenario: A test that the agent removes
- **WHEN** the model replaces a test file with a file that holds fewer of its tests, and ticks the tasks
- **THEN** the step reports stopped with the reason that names the file and the missing tests, no verification command runs, and the checkout is reset

## ADDED Requirements

### Requirement: A step keeps the tests that existed
Every test that a `.py` file under `tests/` held at the commit where the step started SHALL be in the checkout after the run, by qualified name (`test_x` or `Class.test_x`), unless the same qualified name is new in another changed test file. A test is a function named `test_*`. When a test is lost, the step SHALL stop with a reason that names the file and at most `CONST_ROADMAP_IMPLEMENT_REASON_TESTS` of its tests, and SHALL give no extra turn. A file that does not parse is skipped.

#### Scenario: A test file that the agent replaces
- **WHEN** a test file holds `test_a` and `test_b` at the start, and the model writes a file that holds `test_c`
- **THEN** the step reports stopped, the reason names the file, `test_a` and `test_b`, and the checkout is reset

#### Scenario: A test that the agent adds
- **WHEN** the model adds `test_c` to a test file that holds `test_a` and `test_b`
- **THEN** the step reports done

#### Scenario: A test that the agent renames
- **WHEN** the model renames `test_a` to `test_z` in its file
- **THEN** the step reports stopped, and the reason names `test_a`

#### Scenario: A test file that the agent deletes
- **WHEN** the model deletes a test file that holds `test_a`
- **THEN** the step reports stopped, and the reason names the file and `test_a`

#### Scenario: A test that the agent moves
- **WHEN** the model moves `Check.test_a` from one test file to a new test file
- **THEN** the step reports done

#### Scenario: A file that does not parse
- **WHEN** a test file has a syntax error after the run, or at the start
- **THEN** this check does not stop the step, and the static check judges the file

#### Scenario: A long list of lost tests
- **WHEN** the model drops more than `CONST_ROADMAP_IMPLEMENT_REASON_TESTS` tests of a file
- **THEN** the reason names that many tests in order and gives the count of the rest
