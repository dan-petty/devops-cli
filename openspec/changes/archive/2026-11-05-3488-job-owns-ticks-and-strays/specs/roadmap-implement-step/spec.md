## ADDED Requirements

### Requirement: The job ticks the tasks of a group whose exit checks pass
When every exit check of a group step passes, the job SHALL tick each unticked task of the group in the `tasks.md` of the change, and SHALL stage the file, so that the commit holds the ticks. The job SHALL tick a task that the model did not tick. A group with no verification command SHALL be ticked when its exit checks pass. A fix step SHALL tick no task. A step whose exit check fails SHALL write no tick.

#### Scenario: A passing group with no tick from the model
- **WHEN** the model writes the test file and the source file of group 1, ticks no task, and the verification command, `ruff` and `mypy` exit 0
- **THEN** the step reports done, and the commit holds the test file, the source file and `tasks.md` with the tasks of group 1 ticked

#### Scenario: A group with no verification command
- **WHEN** group 1 has no `Verification:` line, the model writes its files and ticks no task, and `ruff` and `mypy` exit 0
- **THEN** the step reports done, and the commit holds the tasks of group 1 ticked

#### Scenario: A failed check after the work
- **WHEN** the model writes the files and ticks no task, and `ruff check` exits 1 in every turn
- **THEN** the step reports stopped, the checkout holds no tick, and the checkout is reset

#### Scenario: A fix step
- **WHEN** a fix step ends with a changed file and no ticks
- **THEN** the step commits the fix, and the job ticks no task

#### Scenario: A tasks file that holds no group to tick
- **WHEN** the `tasks.md` of the change holds no group with the number of the step when the exit checks pass
- **THEN** the step reports stopped with the reason that the job cannot tick the group, and the checkout is reset

## MODIFIED Requirements

### Requirement: A failed exit check stops the step and resets the checkout
The exit checks SHALL run in this order: the agent made no commit, no test from the start is lost, each verification command passes, the static checks pass, and the hooks pass. Then the job ticks the group, as the requirement of the job ticks says. The step SHALL stop at the first check that fails, name it as the reason, make no step commit, and reset the checkout to its last `wip:` commit, or to its start. A failed static check or hook first gets the extra turns of its own requirement.

#### Scenario: A verification command fails
- **WHEN** the model ends its run with the files written and the tasks ticked, and the verification command exits 1
- **THEN** the step reports stopped, the reason names the command and its exit status, the checkout holds no new commit, and the written files are gone

#### Scenario: A static check fails
- **WHEN** the verification command exits 0 and `ruff check` exits 1 on the changed file, in the first turn and in every extra turn
- **THEN** the step reports stopped with the reason that `ruff check` failed, makes no step commit and resets the checkout to its last `wip:` commit

#### Scenario: A task stays unticked
- **WHEN** the model ends its run and leaves a task of the group unticked, and an exit check of the group fails
- **THEN** the job writes no tick, the step reports stopped, and the checkout is reset

#### Scenario: A task stays unticked and a verification command fails
- **WHEN** the model ends its run and leaves a task of the group unticked, and the verification command exits 1
- **THEN** the step reports stopped with the reason that names the command and its exit status, the model gets no extra turn, and the checkout is reset

#### Scenario: The model changes another group
- **WHEN** the model changes the text of a task of group 2 while it works on group 1
- **THEN** the step reports done, and the commit holds group 2 as it was

#### Scenario: A task that the agent removes
- **WHEN** the model removes a task of group 1 from the `tasks.md` and ticks the others
- **THEN** the step restores the tasks of group 1 as they were before the run, and the job ticks them when the exit checks pass

#### Scenario: A task that the agent moves
- **WHEN** the model swaps the texts of two tasks of group 1 and ticks them
- **THEN** the step reports done, and the commit holds the tasks in their order from before the run, ticked

#### Scenario: A heading that the agent changes
- **WHEN** the model changes the heading of group 1
- **THEN** the step reports done, and the commit holds the heading from before the run

#### Scenario: A tasks file that is gone
- **WHEN** the model removes the `tasks.md` of the change
- **THEN** the step writes the file from before the run, and the job ticks the group when the exit checks pass

#### Scenario: A verification command outside the allowlist
- **WHEN** a Verification line of the group names `curl http://example.com`
- **THEN** the step reports stopped, the reason names `curl` as not allowed, the command does not run, and the checkout is reset

#### Scenario: A test that the agent removes
- **WHEN** the model replaces a test file with a file that holds fewer of its tests, and ticks the tasks
- **THEN** the step reports stopped with the reason that names the file and the missing tests, no verification command runs, and the checkout is reset

### Requirement: A refused key stops the whole run
A model call that fails with a `ModelHTTPError` of the status 401 or 403 SHALL raise `AICredentialsError` out of the step after the checkout is reset, and the job SHALL NOT run the next item.

#### Scenario: A refused key in the first turn
- **WHEN** the model call raises a `ModelHTTPError` with the status 401
- **THEN** `run_step` raises `AICredentialsError` and the checkout is reset

#### Scenario: A refused key in the extra turn
- **WHEN** the first turn fails `ruff check`, and the model call of the extra turn raises a `ModelHTTPError` with the status 401 or 403
- **THEN** `run_step` raises `AICredentialsError` and the checkout is reset

#### Scenario: A refused key in a job
- **WHEN** the model call of the first step of an item raises a `ModelHTTPError` with the status 401
- **THEN** `apply_implement` raises `AICredentialsError`, and the item gets no stop comment

### Requirement: An error of the generation inside a stream is sent again
When a model call fails with a `ModelHTTPError` of the status 400 inside an open stream that is no context window error, the step SHALL send the request again with the same history, at most `CONST_ROADMAP_IMPLEMENT_MODEL_RESENDS` times in a row. A send that gets a reply SHALL give the next failed request its own resends. The limits SHALL count the failed requests too. After the last send, the step SHALL stop with the reason of a failed model call.

#### Scenario: Two separate failures
- **WHEN** a model request fails with a 400 inside a stream, a good reply follows, a later request fails the same way, and the next send answers with a good reply
- **THEN** each failed request is sent again, and the step ends done

#### Scenario: One failed send
- **WHEN** the first model request fails with a 400 inside a stream, and the second request answers with a good reply that ends the run
- **THEN** the step ends done, and the second request holds the same messages as the first

#### Scenario: Every send fails
- **WHEN** every model request fails with a 400 inside a stream with the body "XML syntax error on line 75: unexpected EOF"
- **THEN** the step stops, the reason holds the body, and the model got `CONST_ROADMAP_IMPLEMENT_MODEL_RESENDS` plus one requests

#### Scenario: Other failed model calls
- **WHEN** a model request fails with a 400 that is not inside a stream, a 503, or a 400 that is a context window error
- **THEN** the model gets no second request, and the step stops

#### Scenario: The failed send counts in the limit
- **WHEN** the replies and the failed send reach `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS`
- **THEN** the model gets no more than that many requests, and the step stops with the reason of the request limit

#### Scenario: A failure in the extra turn
- **WHEN** the model request of the extra turn for a failed static check fails once with a 400 inside a stream
- **THEN** the request is sent again, and the extra turn ends with the check passing

### Requirement: A failure that no attempt can fix gets no repair round
A failure of the class `plan_defect` or `premise_false` SHALL get no repair round, whatever the setting `repair_rounds` is. The step SHALL stop with the evidence of the failure. Only a failed static check or hook gets a round.

#### Scenario: A group that changes no file
- **WHEN** the model ends its run and changes no file of a group
- **THEN** the step reports stopped with the class `plan_defect`, the model got one run and no extra turn, and the trace holds one attempt

### Requirement: A step writes tasks.md back to its text before the run
After each turn of the model, the step SHALL write the `tasks.md` of the change back as it was before the run, with each task of its own group ticked that the model ticked, by position. The step SHALL tick none when the model changed the number of the tasks of the group. A fix step SHALL tick none.

#### Scenario: The model ticks two groups and edits a task of the later one
- **WHEN** the model works on group 1, ticks the tasks of groups 1 and 2, and deletes the number "2.1" from a task of group 2
- **THEN** the step reports done, and the commit holds `tasks.md` as before the run with only the tasks of group 1 ticked, and the step prints one line that names the change

#### Scenario: The model ticks a later group
- **WHEN** the model completes group 1, ticks its tasks and the tasks of group 2, and ends its run
- **THEN** the step reports done, and the commit holds group 1 ticked and group 2 unticked

#### Scenario: The model unticks an earlier group
- **WHEN** the model works on group 2, ticks its tasks, and unticks a task of group 1, which was ticked
- **THEN** the step reports done, and the commit holds group 1 as it was

#### Scenario: The model rewrites the text of a task and ticks it
- **WHEN** the model rewrites the text of task 1.1 and ticks the tasks of group 1
- **THEN** the step reports done, and the commit holds the text from before the run with the tasks of group 1 ticked

#### Scenario: The model rewrites the text in the extra turn
- **WHEN** the model rewrites the text of an unticked task in the extra turn, ticks it, and the exit checks pass
- **THEN** the step reports done, and the commit holds the text from before the run with the task ticked

#### Scenario: The model rewrites a verification command to one that passes
- **WHEN** the model replaces the command of a `Verification:` line of group 1 with a command that exits 0, and the original command exits 1
- **THEN** the step runs only the original command, reports stopped, the reason names the original command, and the checkout is reset

#### Scenario: The model adds, removes or reorders groups or tasks
- **WHEN** the model adds a group, removes a group, swaps two tasks of group 2, or adds a section outside every group, and ticks the tasks of group 1
- **THEN** the step reports done, and the commit holds the structure from before the run with group 1 ticked

#### Scenario: The model ticks part of the group
- **WHEN** the model ticks one of the two tasks of group 1, and the exit checks pass
- **THEN** the step reports done, and the commit holds both tasks of group 1 ticked

#### Scenario: The model changes the number of the tasks of its group
- **WHEN** the model adds a task to group 1 and ticks every task of the group, and the exit checks pass
- **THEN** the step restores the tasks of group 1 as they were before the run, and the commit holds them ticked

#### Scenario: The model removes or garbles the file
- **WHEN** the model removes `tasks.md`, or writes bytes that are not UTF-8 to it, and ticks nothing else
- **THEN** the step writes the file from before the run, and the job ticks the group when the exit checks pass

#### Scenario: A link or a directory in place of the file
- **WHEN** the model replaces `tasks.md` with a link to a file that holds the text to write, or with a directory
- **THEN** the step removes the link or the directory and writes the file, and the commit holds a regular file

#### Scenario: A file with CRLF or lone CR line ends
- **WHEN** the `tasks.md` has CRLF line ends, or many lone CR line ends before the groups, and the model ticks its group and a later group
- **THEN** the committed `tasks.md` keeps those line ends, the group is ticked on its own lines, and the later group is unticked

#### Scenario: A tick and nothing else
- **WHEN** the last line of group 1 ends with two spaces and the model only ticks its tasks
- **THEN** the step reports done, the commit holds the two spaces, and the step prints no line

#### Scenario: A fix step edits a task
- **WHEN** a fix step ticks a task of any group, or edits the text of a task
- **THEN** the step reports done, and the commit holds `tasks.md` as it was

#### Scenario: A tasks file that numbers a group twice
- **WHEN** the `tasks.md` of the change holds two groups with the number 2
- **THEN** the step is refused before the model runs, and the message names the change and group 2

#### Scenario: The model edits a line that is not a tick
- **WHEN** the model edits a line of the file that is not a tick
- **THEN** the step prints one line that names the change, and the step does not stop for the edit

#### Scenario: A file numbers a group twice
- **WHEN** the tasks file numbers a group twice before the run
- **THEN** the step refuses the file before it starts

### Requirement: A step removes the stray files of the agent
Before the exit checks stage the checkout, and again after the extra turn, the step SHALL unstage and delete each stray file and SHALL give it to no tool. A stray file is an untracked or added file that git does not ignore, a nested git repository, or a file that the group does not allow.

#### Scenario: A scratch file in the root
- **WHEN** the model writes `tmp_test_x.py` with an unused import in the checkout root, writes the files of the group, ticks the tasks, and ends its run
- **THEN** the step reports done, the file is not in the tree or in the commit, no tool got its name, and `removed` lists `tmp_test_x.py`

#### Scenario: A new test file in the directory of the group
- **WHEN** the model writes `tests/test_sample_more.py` next to the named `tests/test_sample.py`
- **THEN** the step keeps the file, and the commit holds it

#### Scenario: A file of the project directories that the plan does not list
- **WHEN** the model writes `tests/data.json`, `tests/conftest.py` and `src/helper.py`, which the group does not name
- **THEN** the step keeps the files, ends done, and the commit holds them

#### Scenario: A nested git repository
- **WHEN** the model runs `git init sub` and writes `sub/a.txt`
- **THEN** the step removes `sub/` with its files, lists `sub/` in `removed`, and ends done

#### Scenario: A fix step
- **WHEN** a fix step runs and the model writes a new file outside `src/`, `tests/`, `docs/` and `openspec/`
- **THEN** the step deletes the file

#### Scenario: A fix step with a new test file
- **WHEN** a fix step runs and the model writes a new file under `tests/`
- **THEN** the step keeps the file and stages it

#### Scenario: A staged stray file
- **WHEN** the agent stages a new file outside `src/`, `tests/`, `docs/` and `openspec/` with `git add`
- **THEN** the step unstages the file and deletes it, in a group step and in a fix step

#### Scenario: A staged rename into a stray name
- **WHEN** the agent renames `src/other.py` to `tmp_test_x.py` with `git mv`
- **THEN** the step unstages and deletes `tmp_test_x.py`, and puts back `src/other.py`, so that the commit and the work in progress keep the file

#### Scenario: A file in a directory that the group does not name
- **WHEN** the model writes `scripts/probe.py`, which the group does not name
- **THEN** the step deletes the file

#### Scenario: The agent is told
- **WHEN** a scratch file was removed and `ruff check` fails on a file of the group
- **THEN** the message of the extra turn names the removed file and says that the group does not name it

#### Scenario: A stray file in the extra turn
- **WHEN** the model writes a scratch file in the extra turn
- **THEN** the step deletes it, and does not stop for a file that it had not changed

#### Scenario: An ignored file
- **WHEN** the model writes a file under `.data/agent/scratch/`
- **THEN** the step does not list it, deletes nothing, and the commit holds no such file

#### Scenario: The paths that a group allows
- **WHEN** the group names a path in a code span, and the model writes files under its change folder, under `src/`, `tests/`, `docs/` or `openspec/`, and at the named path
- **THEN** the step keeps those files, and it names each removed file in the Job log, in `StepOutcome.removed` and in the extra turn

### Requirement: A step keeps a ticked task whose verification passes
When the agent ticks a task of the group, the step SHALL run the verification commands of that task, as the text of the `tasks.md` before the run gives them. When they pass, or the task has none, the step SHALL commit the checkout as `wip: <done> of <total> tasks of group <n>, <title> (#<issue>)` and tell its caller through `on_wip`. A task that fails its verification SHALL NOT be kept, and a fix step SHALL keep nothing.

#### Scenario: Two tasks, one ticked
- **WHEN** the model writes the test, ticks the first task, writes the code of the second task, ends without a tick for it, and the verification command `uv run devops docs check` of the group exits 1 at the exit
- **THEN** the step reports stopped, the checkout holds one `wip:` commit with the test and the first task ticked, the code of the second task is gone, and `on_wip` was called once with 1 of 2

#### Scenario: A task that fails its verification
- **WHEN** the model ticks the first task and its verification command exits 1
- **THEN** the step makes no `wip:` commit and calls no `on_wip`

#### Scenario: A lint error after the last tick
- **WHEN** the model ticks every task, each verification passes, and `ruff check` fails at the exit
- **THEN** the step reports stopped, and the checkout holds one `wip:` commit with the work and the ticks

## REMOVED Requirements

### Requirement: A step asks for the missing ticks within the repair rounds
**Reason**: The job ticks the group at its exit, so a missing tick gets no extra turn.
**Migration**: The requirement "The job ticks the tasks of a group whose exit checks pass" holds the ticks of a group.

### Requirement: The turn for the ticks changes only the tasks file
**Reason**: No turn asks for a tick, so no turn for the ticks exists.
**Migration**: The requirement "The turn for a failed static check changes only the files of the step" holds the rule of a repair turn, and the job writes `tasks.md` itself.

### Requirement: The reason of the turn for the ticks names a bounded number of paths
**Reason**: No turn for the ticks exists.
**Migration**: The requirement "The turn for a failed static check changes only the files of the step" names the other paths of a repair turn.

### Requirement: A step asks for a fix of a failed check within the repair rounds
**Reason**: The requirement names its scenarios after the ticks, and the repair turn of a failed static check or hook has its own name now.
**Migration**: The requirement "A step asks for a fix of a failed static check or hook within the repair rounds" holds the same rule.

## ADDED Requirements

### Requirement: A step asks for a fix of a failed static check or hook within the repair rounds
When the agent ends its run, each verification command passes, and `ruff check`, `mypy --strict` or a hook fails, the step SHALL run one more turn in the same conversation under the same `UsageLimits`, while a repair round is left. Its message SHALL hold the failure text, masked and cut to `CONST_ROADMAP_IMPLEMENT_REASON_CHARS` characters. Every exit check SHALL run again after each turn. With no round left the step SHALL stop with the last failure.

#### Scenario: An unused import
- **WHEN** the model ticks the tasks and ends its run, `ruff check` exits 1 for an unused import in a changed file, and the model removes the import in the extra turn
- **THEN** the step reports done, the extra turn got the text of the failure, the commit holds the file without the import, `ruff check` ran twice, and `repair_rounds` is 1

#### Scenario: The failure stays
- **WHEN** `ruff check` still exits 1 after every round, and `repair_rounds` is 3
- **THEN** the step reports stopped with the reason that names `ruff check` and its exit status, the model got three extra turns and no fourth, and the checkout is reset

#### Scenario: A failed type check
- **WHEN** `mypy --strict` exits 1 after the first turn, and the model fixes the file in the extra turn
- **THEN** the step reports done, and the extra turn got the text of the failure of `mypy`

#### Scenario: A failure with a task left unticked
- **WHEN** `ruff check` exits 1 after the first turn, and a task of the group is unticked
- **THEN** the message of the extra turn holds the text of the failure and no list of tasks, and the job ticks the group when the repair passes the checks

#### Scenario: A failed verification command
- **WHEN** a verification command exits 1
- **THEN** the model gets no extra turn for it

#### Scenario: A failure after the repair turn
- **WHEN** the extra turn for the failed check ends and `ruff check` exits 1
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
