## MODIFIED Requirements

### Requirement: A step asks for a fix of a failed check within the repair rounds
When a verification command that is no negative search exits 1, or a static check or hook fails, the step SHALL run one more turn under the same `UsageLimits`, while a repair round is left. Its message SHALL hold the class, the failure text masked and cut to `CONST_ROADMAP_IMPLEMENT_REASON_CHARS` characters, and a diagnosis hint. Every exit check SHALL run again after each turn. With no round left the step SHALL stop with the last failure.

#### Scenario: An unused import
- **WHEN** the model ticks the tasks and ends its run, `ruff check` exits 1 for an unused import in a changed file, and the model removes the import in the extra turn
- **THEN** the step reports done, the extra turn got the text of the failure, the commit holds the file without the import, `ruff check` ran twice, and `repair_rounds` is 1

#### Scenario: The failure stays
- **WHEN** `ruff check` still exits 1 after every round, and `repair_rounds` is 3
- **THEN** the step reports stopped with the reason that names `ruff check`, its exit status and the three spent rounds, the model got three extra turns and no fourth, and the checkout is reset

#### Scenario: A failed type check
- **WHEN** `mypy --strict` exits 1 after the first turn, and the model fixes the file in the extra turn
- **THEN** the step reports done, and the extra turn got the text of the failure of `mypy`

#### Scenario: A failure with a task left unticked
- **WHEN** `ruff check` exits 1 after the first turn, and a task of the group is unticked
- **THEN** the message of the extra turn holds the text of the failure and no list of tasks, and the job ticks the group when the repair passes the checks

#### Scenario: A failed verification command
- **WHEN** the verification command `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step_attempts.py` exits 1, and the model fixes the failing test in the extra turn
- **THEN** the step reports done, the message of the extra turn names the class `test` and holds the output of the command, and the trace holds one attempt for the failure and one attempt for the repair

#### Scenario: A failure after the repair turn
- **WHEN** the extra turn for the failed check ends and `ruff check` exits 1
- **THEN** the model gets another turn that holds the text of the failure, while a round is left

#### Scenario: No round
- **WHEN** `repair_rounds` is 0 and `ruff check` exits 1
- **THEN** the model gets no extra turn and the step reports stopped with the reason that names `ruff check` and the zero spent rounds

#### Scenario: A fix step
- **WHEN** a fix step ends with a changed file and `ruff check` exits 1
- **THEN** the model gets an extra turn that holds the text of the failure and no list of ticks

#### Scenario: The extra turn shares the budget
- **WHEN** the first turn used all but one of the model requests and the extra turn needs two
- **THEN** the step reports stopped with a reason that starts with `UsageLimitExceeded: `

#### Scenario: A hook fails
- **WHEN** the `pre-commit` stage exits 1 for a test that calls a raising function with no match, in a changed test, and the model adds the match in the extra turn
- **THEN** the step reports done, the message of the extra turn holds the output of the hook, and the commit holds the fixed test

#### Scenario: A hook that the agent cannot fix
- **WHEN** the `pre-commit` stage exits 1 after every turn, and the repair rounds are set to 3
- **THEN** the step reports stopped with the reason that holds the output of the hook, the model got three extra turns, the repair rounds are 3, and the checkout is reset

### Requirement: A step keeps the tests that existed
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

#### Scenario: A kept task with a recorded removal
- **WHEN** the agent ticks a task whose verification passes, and the only test that it lost is in `recorded_tests`
- **THEN** the keeper makes the `wip:` commit

#### Scenario: The prompt of the step
- **WHEN** a test reads the prompt of the step
- **THEN** the rule of the tests names the `## Weakened checks` section, and says that an entry from the agent does not count

#### Scenario: A lost test that the repair restores
- **WHEN** the model removes `test_a` from a test file that existed at the base commit, and the extra turn restores it
- **THEN** the step reports done, the extra turn got the reason that names the file and `test_a`, and the trace holds one attempt for the lost test and one attempt for the repair

### Requirement: A failed exit check stops the step and resets the checkout
The exit checks SHALL run in this order: the agent made no commit, no test from the start is lost, each verification command passes, the static checks pass, and the hooks pass. Then the job ticks the group, as the requirement of the job ticks says. The step SHALL stop at the first check that fails, name it as the reason, make no step commit, and reset the checkout to its last `wip:` commit, or to its start. A failed check first gets the extra turns of its own requirement.

#### Scenario: A verification command fails
- **WHEN** the model ends its run with the files written and the tasks ticked, the verification command exits 1, and no round is left
- **THEN** the step reports stopped, the reason names the command, its exit status and the spent rounds, the checkout holds no new commit, and the written files are gone

#### Scenario: A static check fails
- **WHEN** the verification command exits 0 and `ruff check` exits 1 on the changed file, in the first turn and in every extra turn
- **THEN** the step reports stopped with the reason that `ruff check` failed, makes no step commit and resets the checkout to its last `wip:` commit

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

### Requirement: A failure that no attempt can fix gets no repair round
A failure of the class `plan_defect` or `premise_false` SHALL get no repair round, whatever the setting `repair_rounds` is. The step SHALL stop with the evidence of the failure. Only a verification command that exits 1, a lost test, a failed static check or a hook gets a round.

#### Scenario: A group that changes no file
- **WHEN** the model ends its run and changes no file of a group
- **THEN** the step reports stopped with the class plan_defect, the model got one run and no extra turn, and the trace holds one attempt

## RENAMED Requirements

- FROM: `### Requirement: A step asks for a fix of a failed static check or hook within the repair rounds`
- TO: `### Requirement: A step asks for a fix of a failed check within the repair rounds`
