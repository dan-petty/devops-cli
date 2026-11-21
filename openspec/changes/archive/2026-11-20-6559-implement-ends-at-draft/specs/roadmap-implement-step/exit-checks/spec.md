## ADDED Requirements

### Requirement: A step makes the only commit since its start
The first exit check SHALL put `HEAD` back at the commit where the step started, with `git reset --soft` when the agent moved it, so the checkout keeps the work of the agent and the later exit checks judge that work. The step SHALL stop with the class `head_moved` only when the reset exits with a status other than 0.

#### Scenario: A commit by the agent
- **WHEN** the agent commits its work with `git`, and ticks the tasks
- **THEN** the step resets `HEAD` to the commit where it started, prints one muted line that names the moved head and the expected head, and reports done with one commit whose parent is the commit where the step started and that holds the work of the agent

#### Scenario: A failed check after the reset
- **WHEN** the agent commits its work and a later exit check fails
- **THEN** the step reports stopped with the reason of that check, not with the class `head_moved`, makes no commit, and the checkout is back at the commit where the step started

#### Scenario: A reset that fails
- **WHEN** the agent moved `HEAD` and `git reset --soft` to the expected head exits with a status other than 0
- **THEN** the step reports stopped with the class `head_moved`, and the reason names the reset command, its exit status and the output of git

### Requirement: A step keeps the tests that existed at its start
Every test that a `.py` file under `tests/` held at the commit where the step started SHALL be in the checkout after the run, by qualified name (`test_x` or `Class.test_x`), unless `recorded_tests` gives its `path::name`. A test is a function named `test_*`. When another test is lost, the step SHALL give one repair turn while a round is left, and otherwise stop with a reason that names the file and at most `CONST_ROADMAP_IMPLEMENT_REASON_TESTS` of its tests.

#### Scenario: A test file that the agent replaces
- **WHEN** a test file holds `test_a` and `test_b` at the start, the model writes a file that holds `test_c`, and no round is left
- **THEN** the step reports stopped, the reason names the file, `test_a` and `test_b` and the spent rounds, and the checkout is reset

#### Scenario: A test that the agent adds
- **WHEN** the model adds `test_c` to a test file that holds `test_a` and `test_b`
- **THEN** the step reports done

#### Scenario: A test that the agent renames
- **WHEN** the model renames `test_a` to `test_z` in its file, and no round is left
- **THEN** the step reports stopped, and the reason names `test_a`

#### Scenario: A test file that the agent deletes
- **WHEN** the model deletes a test file that holds `test_a`, and no round is left
- **THEN** the step reports stopped, and the reason names the file and `test_a`

#### Scenario: A test that the agent moves
- **WHEN** the model moves `test_a` of a class from one test file to a new test file, and no round is left
- **THEN** the step reports stopped, and the reason names the old file and `test_a`

#### Scenario: A test that loses its body
- **WHEN** the model keeps the name of `test_a` and replaces its body with `pass`
- **THEN** this check does not stop the step: it reads names only

#### Scenario: A file that does not parse
- **WHEN** a test file has a syntax error after the run, or at the start
- **THEN** this check does not stop the step, and the static check judges the file

#### Scenario: A long list of lost tests
- **WHEN** the model drops more than `CONST_ROADMAP_IMPLEMENT_REASON_TESTS` tests of a file
- **THEN** the reason names that many tests in order and gives the count of the rest

#### Scenario: A removal that the record names
- **WHEN** the model removes `test_a`, and `recorded_tests` gives `tests/roadmap/implement/test_roadmap_implement_step_tests_kept.py::test_a`
- **THEN** the step reports done

#### Scenario: A rename or a move that the record names
- **WHEN** the model renames `test_a` to `test_z` or moves it to a new test file, and `recorded_tests` holds the old `path::name`
- **THEN** the step reports done

#### Scenario: A removal that the record does not name
- **WHEN** the model removes `test_a` and `test_b`, and `recorded_tests` gives only the name of `test_a`, and no round is left
- **THEN** the step reports stopped with the class `tests_lost`, and the reason names `test_b` and not `test_a`

#### Scenario: The prompt of the step
- **WHEN** a test reads the prompt of the step
- **THEN** the rule of the tests names the `## Weakened checks` section, and says that an entry from the agent does not count

#### Scenario: A lost test that the repair restores
- **WHEN** the model removes `test_a` from a test file that existed at the base commit, and the extra turn restores it
- **THEN** the step reports done, the extra turn got the reason that names the file and `test_a`, and the trace holds one attempt for the lost test and one attempt for the repair

## MODIFIED Requirements

### Requirement: A failed exit check stops the step and resets the checkout
The exit checks SHALL run in this order: the agent made no commit, no test from the start is lost, each verification command passes, the static checks pass, and the hooks pass. Then the job ticks the group, as the requirement of the job ticks says. The step SHALL stop at the first check that fails, name it as the reason, make no step commit, and reset the checkout to its start. A failed check first gets the extra turns of its own requirement.

#### Scenario: A verification command fails
- **WHEN** the model ends its run with the files written and the tasks ticked, the verification command exits 1, and no round is left
- **THEN** the step reports stopped, the reason names the command, its exit status and the spent rounds, the checkout holds no new commit, and the written files are gone

#### Scenario: A static check fails
- **WHEN** the verification command exits 0 and `ruff check` exits 1 on the changed file, in the first turn and in every extra turn
- **THEN** the step reports stopped with the reason that `ruff check` failed, makes no step commit and resets the checkout to the commit where the step started

#### Scenario: A task stays unticked
- **WHEN** the model ends its run and leaves a task of the group unticked, and an exit check of the group fails
- **THEN** the job writes no tick, the step reports stopped, and the checkout is reset

#### Scenario: A task stays unticked and a verification command fails
- **WHEN** the model ends its run and leaves a task of the group unticked, and the verification command exits 1
- **THEN** the step reports stopped with the reason that names the command and its exit status, the model gets the extra turns and no more, and the checkout is reset

#### Scenario: The model changes another group
- **WHEN** the model changes the text of a task of group 2 while it works on group 1
- **THEN** the step reports done, and the commit holds group 2 as it was

#### Scenario: A task that the agent removes
- **WHEN** the model removes a task of group 1 from the tasks file and ticks the others
- **THEN** the step restores the tasks of group 1 as they were before the run, and the job ticks them when the exit checks pass

#### Scenario: A task that the agent moves
- **WHEN** the model swaps the texts of two tasks of group 1 and ticks them
- **THEN** the step reports done, and the commit holds the tasks in their order from before the run, ticked

#### Scenario: A heading that the agent changes
- **WHEN** the model changes the heading of group 1
- **THEN** the step reports done, and the commit holds the heading from before the run

#### Scenario: A tasks file that is gone
- **WHEN** the model removes the tasks file of the change
- **THEN** the step writes the file from before the run, and the job ticks the group when the exit checks pass

#### Scenario: A verification command outside the allowlist
- **WHEN** a Verification line of the group names `curl http://example.com`
- **THEN** the step reports stopped, the reason names `curl` as not allowed, the command does not run, and the checkout is reset

#### Scenario: A test that the agent removes
- **WHEN** the model replaces a test file with a file that holds fewer of its tests, ticks the tasks, and no round is left
- **THEN** the step reports stopped after the repair turn with the reason that names the file and the missing tests, and the checkout is reset

### Requirement: The turn for a failed static check changes only the files of the step
The turn for a failed static check SHALL change no file except `tasks.md`, the files that the step had changed before the turn, and a file whose content the turn restores to its content at the commit where the step started. The step SHALL check this with git, and SHALL stop with a reason that names the other paths when the turn changed any. A file that the turn deletes and that exists at the commit where the step started SHALL stop the step.

#### Scenario: The turn changes a file that the step did not change
- **WHEN** the model changes `src/other.py` in the extra turn, the step had not changed it, and its content differs from the commit where the step started
- **THEN** the step reports stopped with the reason that names `src/other.py`, makes no commit and resets the checkout

#### Scenario: The turn changes a file that the step changed
- **WHEN** the model changes `src/sample.py` in the extra turn, and the step had changed it
- **THEN** the step checks all exit checks again and does not stop for the change

#### Scenario: The turn restores a file to the base content
- **WHEN** the step changed `src/sample.py`, and the extra turn writes the content that the file has at the commit where the step started
- **THEN** `_foreign_change` returns None and the step continues with the exit checks

#### Scenario: The turn deletes a file of the base
- **WHEN** the extra turn deletes a file outside the allowed set that exists at the commit where the step started
- **THEN** the step stops with a reason that names the deleted file

## REMOVED Requirements

### Requirement: A step makes the only commit
**Reason**: The implement Job makes no work-in-progress commit and no work-in-progress push (#6559).
**Migration**: The requirement "A step makes the only commit since its start" holds the rule.

### Requirement: A step keeps the tests that existed
**Reason**: The implement Job makes no work-in-progress commit and no work-in-progress push (#6559).
**Migration**: The requirement "A step keeps the tests that existed at its start" holds the rule.

### Requirement: A step keeps a ticked task whose verification passes
**Reason**: The implement Job makes no work-in-progress commit and no work-in-progress push (#6559).
**Migration**: A checkpoint pushes each group that passed, and a step that stops resets the checkout to the commit where it started.

### Requirement: A work-in-progress commit holds the tasks file of the job
**Reason**: The implement Job makes no work-in-progress commit and no work-in-progress push (#6559).
**Migration**: None: the step makes no `wip:` commit.

### Requirement: A step that ends done folds its work in progress into its commit
**Reason**: The implement Job makes no work-in-progress commit and no work-in-progress push (#6559).
**Migration**: The step makes one commit when its exit checks pass.
