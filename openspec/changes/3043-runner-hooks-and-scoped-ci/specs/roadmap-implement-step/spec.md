# Spec Delta

## RENAMED Requirements

- FROM: `### Requirement: A step asks once for the missing ticks`
- TO: `### Requirement: A step asks for the missing ticks within the repair rounds`
- FROM: `### Requirement: A step asks once for a fix of a failed static check`
- TO: `### Requirement: A step asks for a fix of a failed check within the repair rounds`

## MODIFIED Requirements

### Requirement: A failed exit check stops the step and resets the checkout
The exit checks SHALL run in this order: the agent made no commit, no test that existed at the start is lost, each verification command passes, the static checks pass, the hooks of the repository pass, and every task of the group is ticked. The step SHALL stop at the first check that fails, name it as the reason, make no commit, and reset the checkout. A failed static check, a failed hook, and a task left unticked after the first five checks, first get the extra turns of their own requirements.

#### Scenario: A verification command fails
- **WHEN** the model ends its run with the files written and the tasks ticked, and the verification command exits 1
- **THEN** the step reports stopped, the reason names the command and its exit status, the checkout holds no new commit, and the written files are gone

#### Scenario: A static check fails
- **WHEN** the verification command exits 0 and `ruff check` exits 1 on the changed file, in the first turn and in every extra turn
- **THEN** the step reports stopped with the reason that `ruff check` failed, makes no commit and resets the checkout

#### Scenario: A task stays unticked
- **WHEN** the model ends its run and leaves a task of the group unticked, the verification command and the static checks exit 0, and every extra turn leaves the task unticked
- **THEN** the step reports stopped, the reason names the unticked task, and the checkout is reset

#### Scenario: A task stays unticked and a verification command fails
- **WHEN** the model ends its run and leaves a task of the group unticked, and the verification command exits 1
- **THEN** the step reports stopped with the reason that names the command and its exit status, the model gets no extra turn, and the checkout is reset

#### Scenario: The model changes another group
- **WHEN** the model changes the text of a task of group 2 while it works on group 1
- **THEN** the step reports done, and the commit holds group 2 as it was

#### Scenario: A task that the agent removes
- **WHEN** the model removes a task of group 1 from the `tasks.md` and ticks the others
- **THEN** the step ticks no task of group 1, gives the extra turn, and stops with the reason that names the first unticked task when the turns change nothing

#### Scenario: A task that the agent moves
- **WHEN** the model swaps the texts of two tasks of group 1 and ticks them
- **THEN** the step reports done, and the commit holds the tasks in their order from before the run, ticked

#### Scenario: A heading that the agent changes
- **WHEN** the model changes the heading of group 1
- **THEN** the step reports done, and the commit holds the heading from before the run

#### Scenario: A tasks file that is gone
- **WHEN** the model removes the `tasks.md` of the change
- **THEN** the step writes the file from before the run, gives the extra turn for the unticked tasks, and stops with the reason that names the first unticked task when the turns change nothing

#### Scenario: A verification command outside the allowlist
- **WHEN** a Verification line of the group names `curl http://example.com`
- **THEN** the step reports stopped, the reason names `curl` as not allowed, the command does not run, and the checkout is reset

#### Scenario: A test that the agent removes
- **WHEN** the model replaces a test file with a file that holds fewer of its tests, and ticks the tasks
- **THEN** the step reports stopped with the reason that names the file and the missing tests, no verification command runs, and the checkout is reset

### Requirement: A step asks for the missing ticks within the repair rounds
When the agent ends its run, the check of the tasks passes, each verification command passes, the static checks and the hooks pass, and a task of the group is unticked, the step SHALL run one more model turn while a repair round is left. The turn SHALL continue the same conversation under the same `UsageLimits`. Its message SHALL name the path of the `tasks.md` and list the unticked tasks, and SHALL ask only for their ticks. A step SHALL get at most `roadmap.implement.repair_rounds` extra turns in all, whichever check asks for them, and none for the ticks of a fix step.

#### Scenario: The agent forgot the ticks
- **WHEN** the model writes a test file and a source file, ends its run with the tasks of group 1 unticked, the verification command and the static checks exit 0, and the model ticks the tasks in the extra turn
- **THEN** the step reports done, the extra turn got the list of the unticked tasks, the new commit holds the test file, the source file and the ticked `tasks.md`, and the verification command ran twice

#### Scenario: The turn ticks nothing
- **WHEN** the model ends every extra turn and leaves the task unticked, and `repair_rounds` is 2
- **THEN** the step reports stopped with the reason that names the unticked task, and the model got two extra turns and no third

#### Scenario: A fix step
- **WHEN** a fix step ends with a changed file and no ticks
- **THEN** the step commits the fix and the model gets no extra turn

### Requirement: A step asks for a fix of a failed check within the repair rounds
When the agent ends its run, each verification command passes, and `ruff check`, `mypy --strict` or a hook of the repository fails, the step SHALL run one more turn in the same conversation under the same `UsageLimits`, while a repair round is left. Its message SHALL hold the text of the failure and the unticked tasks, if any. The step SHALL mask secrets in the text with `mask_secrets` first, then cut it to `CONST_ROADMAP_IMPLEMENT_REASON_CHARS` characters. Every exit check SHALL run again after each turn. The step SHALL stop with the failure of the last run when no round is left. `StepOutcome.repair_rounds` SHALL count the extra turns.

#### Scenario: An unused import
- **WHEN** the model ticks the tasks and ends its run, `ruff check` exits 1 for an unused import in a changed file, and the model removes the import in the extra turn
- **THEN** the step reports done, the extra turn got the text of the failure, the commit holds the file without the import, `ruff check` ran twice, and `repair_rounds` is 1

#### Scenario: The failure stays
- **WHEN** `ruff check` still exits 1 after every round, and `repair_rounds` is 3
- **THEN** the step reports stopped with the reason that names `ruff check` and its exit status, the model got three extra turns and no fourth, and the checkout is reset

#### Scenario: A failed type check
- **WHEN** `mypy --strict` exits 1 after the first turn, and the model fixes the file in the extra turn
- **THEN** the step reports done, and the extra turn got the text of the failure of `mypy`

#### Scenario: A failure and an unticked task
- **WHEN** `ruff check` exits 1 after the first turn, and a task of the group is unticked
- **THEN** the message of the extra turn holds the text of the failure and the unticked task

#### Scenario: The ticks stay missing
- **WHEN** the extra turn fixes the static failure and leaves a task unticked
- **THEN** the next turn asks only for the ticks, and the step stops with the reason that names the unticked task when no round is left

#### Scenario: A failed verification command
- **WHEN** a verification command exits 1
- **THEN** the model gets no extra turn for it

#### Scenario: A failure after the turn for the ticks
- **WHEN** the extra turn for the ticks ends and `ruff check` exits 1
- **THEN** the model gets another turn that holds the text of the failure, while a round is left

#### Scenario: No round
- **WHEN** `repair_rounds` is 0 and `ruff check` exits 1
- **THEN** the model gets no extra turn and the step reports stopped with the reason that names `ruff check`

#### Scenario: A fix step
- **WHEN** a fix step ends with a changed file and `ruff check` exits 1
- **THEN** the model gets an extra turn that holds the text of the failure and no list of ticks

#### Scenario: The extra turn shares the budget
- **WHEN** the first turn used all but one of the model requests and the extra turn needs two
- **THEN** the step reports stopped with a reason that starts with `UsageLimitExceeded: `

#### Scenario: A hook fails
- **WHEN** the `pre-commit` stage exits 1 for a `pytest.raises` with no `match` in a changed test, and the model adds the `match` in the extra turn
- **THEN** the step reports done, the message of the extra turn holds the output of the hook, and the commit holds the fixed test

#### Scenario: A hook that the agent cannot fix
- **WHEN** the `pre-commit` stage exits 1 after every turn, and `repair_rounds` is 3
- **THEN** the step reports stopped with the reason that holds the output of the hook, the model got three extra turns, `repair_rounds` is 3, and the checkout is reset

### Requirement: The outcome is a structured report
The step SHALL return a `StepOutcome` with the status (done or stopped), the reason, the last message of the agent, the commit, the repair rounds used, and the requests, the tool calls and the tokens that the run spent. The command SHALL print it as a table, or as JSON with `--format json`, and SHALL exit 1 when the status is stopped. The step SHALL record the spend of the run as one record of the spend ledger.

#### Scenario: A stopped step as JSON
- **WHEN** a step stops on a failed verification and the command runs with `--format json`
- **THEN** the output is one JSON object with `status` `stopped`, the reason, an empty `commit`, and the counts of requests, tool calls and tokens, and the exit code is 1

#### Scenario: The spend record
- **WHEN** a step ends after two model requests
- **THEN** the spend ledger holds one record for the run with the sum of the tokens of the two replies

#### Scenario: The tool calls
- **WHEN** a step ends after three tool calls in two replies
- **THEN** the outcome holds `tool_calls` 3

#### Scenario: The repair rounds
- **WHEN** a step ends after one extra turn
- **THEN** the outcome holds `repair_rounds` 1 and the table shows the count

## ADDED Requirements

### Requirement: The hooks of the repository are an exit check
After the static checks, the step SHALL run the `pre-commit` stage of the hooks of the repository over the staged changes, with `pre-commit run --hook-stage pre-commit`. The child SHALL hold no GitHub token and SHALL have `PRE_COMMIT_HOME` under the data directory. The step SHALL install no git hook. The step SHALL run no hook when the commit at the start of the step holds no `.pre-commit-config.yaml`; a file that the agent removes SHALL NOT change that.

#### Scenario: No hook configuration
- **WHEN** the repository holds no `.pre-commit-config.yaml` and the checks pass
- **THEN** the step reports done and runs no `pre-commit` command

#### Scenario: A configuration that the agent removes
- **WHEN** the commit holds the configuration and the agent deletes the file
- **THEN** the step still runs the stage, which fails, and the agent gets a repair turn

#### Scenario: No git hook
- **WHEN** a step ends done
- **THEN** the checkout holds no `pre-commit` or `pre-push` file in its git hooks directory, and the child that ran the hooks got no variable that matches `*TOKEN*`

### Requirement: A hook that fixes a file runs again, and exit 1 is the only repairable failure
When a hook changes a file, the step SHALL stage the changed files and run the stage once more. Exit code 1 of the second run SHALL be a failure that the agent may repair, with the output of the hooks as its text. Any other non-zero exit code SHALL stop the step with the output.

#### Scenario: A hook changes a file
- **WHEN** a hook adds the missing newline at the end of a changed file and exits 1, and the second run exits 0
- **THEN** the step reports done, the commit holds the file with the newline, and the model got no extra turn

#### Scenario: A hook fails
- **WHEN** the `pre-commit` stage exits 1 on both runs
- **THEN** the failure goes to the extra turn with the output of the hooks, and the turn may change only the files that the step changed

#### Scenario: A broken environment
- **WHEN** the `pre-commit` stage exits 3
- **THEN** the step reports stopped with the output as the reason, and the model gets no extra turn
