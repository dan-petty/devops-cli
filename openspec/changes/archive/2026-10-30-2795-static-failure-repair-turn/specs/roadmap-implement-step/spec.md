# Spec Delta

## MODIFIED Requirements

### Requirement: A failed exit check stops the step and resets the checkout
The exit checks SHALL run in this order: the agent made no commit, each verification command passes, the static checks pass, and every task of the group is ticked. The step SHALL stop at the first check that fails, name it as the reason, make no commit, and reset the checkout. A failed static check, and a task left unticked after the first three checks, first get the extra turn of their own requirements.

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

### Requirement: A step asks once for the missing ticks
When the agent ends its run, the check of the tasks passes, each verification command passes, the static checks pass, and a task of the group is unticked, the step SHALL run one more model turn. The turn SHALL continue the same conversation under the same `UsageLimits`. Its message SHALL name the path of the `tasks.md` and list the unticked tasks, and SHALL ask only for their ticks. A step SHALL get one extra turn at most, whichever check asks for it, and none for the ticks of a fix step.

#### Scenario: The agent forgot the ticks
- **WHEN** the model writes a test file and a source file, ends its run with the tasks of group 1 unticked, the verification command and the static checks exit 0, and the model ticks the tasks in the extra turn
- **THEN** the step reports done, the extra turn got the list of the unticked tasks, the new commit holds the test file, the source file and the ticked `tasks.md`, and the verification command ran twice

#### Scenario: The turn ticks nothing
- **WHEN** the model ends the extra turn and leaves the task unticked
- **THEN** the step reports stopped with the reason that names the unticked task, and the model got no third turn

#### Scenario: A fix step
- **WHEN** a fix step ends with a changed file and no ticks
- **THEN** the step commits the fix and the model gets no extra turn

## ADDED Requirements

### Requirement: A step asks once for a fix of a failed static check
When the agent ends its run, each verification command passes, and `ruff check` or `mypy --strict` fails, the step SHALL run one more turn in the same conversation under the same `UsageLimits`. Its message SHALL hold the text of the failure and the unticked tasks, if any. The step SHALL mask secrets in the text with `mask_secrets` first, then cut it to `CONST_ROADMAP_IMPLEMENT_REASON_CHARS` characters. The step SHALL run the turn at most once. Every exit check SHALL run again after it.

#### Scenario: An unused import
- **WHEN** the model ticks the tasks and ends its run, `ruff check` exits 1 for an unused import in a changed file, and the model removes the import in the extra turn
- **THEN** the step reports done, the extra turn got the text of the failure, the commit holds the file without the import, and `ruff check` ran twice

#### Scenario: The failure stays
- **WHEN** `ruff check` still exits 1 after the extra turn
- **THEN** the step reports stopped with the reason that names `ruff check` and its exit status, the model got no third turn, and the checkout is reset

#### Scenario: A failed type check
- **WHEN** `mypy --strict` exits 1 after the first turn, and the model fixes the file in the extra turn
- **THEN** the step reports done, and the extra turn got the text of the failure of `mypy`

#### Scenario: A failure and an unticked task
- **WHEN** `ruff check` exits 1 after the first turn, and a task of the group is unticked
- **THEN** the message of the extra turn holds the text of the failure and the unticked task, and the model gets one extra turn

#### Scenario: The ticks stay missing
- **WHEN** the extra turn fixes the static failure and leaves a task unticked
- **THEN** the step reports stopped with the reason that names the unticked task, and the model gets no third turn

#### Scenario: A failed verification command
- **WHEN** a verification command exits 1
- **THEN** the model gets no extra turn for it

#### Scenario: A failure after the turn for the ticks
- **WHEN** the extra turn for the ticks ends and `ruff check` exits 1
- **THEN** the step reports stopped with the reason that names `ruff check`, and the model gets no second extra turn

#### Scenario: A fix step
- **WHEN** a fix step ends with a changed file and `ruff check` exits 1
- **THEN** the model gets one extra turn that holds the text of the failure and no list of ticks

#### Scenario: The extra turn shares the budget
- **WHEN** the first turn used all but one of the model requests and the extra turn needs two
- **THEN** the step reports stopped with a reason that starts with `UsageLimitExceeded: `

### Requirement: The turn for a failed static check changes only the files of the step
The turn for a failed static check SHALL change no file except `tasks.md` and the files that the step had changed before the turn. The step SHALL check this with git, and SHALL stop with a reason that names the other paths when the turn changed any.

#### Scenario: The turn changes a file that the step did not change
- **WHEN** the model changes `src/other.py` in the extra turn, and the step had not changed it
- **THEN** the step reports stopped with the reason that names `src/other.py`, makes no commit and resets the checkout

#### Scenario: The turn changes a file that the step changed
- **WHEN** the model changes `src/sample.py` in the extra turn, and the step had changed it
- **THEN** the step checks all exit checks again and does not stop for the change
