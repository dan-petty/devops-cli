# roadmap-implement-step/exit-checks Specification

## Purpose
The exit checks of an implement step: the commit of a group when the checks pass, the hooks, the type check and the formatter, the tests that a step keeps, and the fix of a failed check.

## Requirements

### Requirement: A step commits its group when the exit checks pass
`devops roadmap implement --item N --group n` SHALL run one agent on group n of the `tasks.md` of the change of item N in the checkout. When the agent returns and every exit check passes, the step SHALL commit the checkout as `<group title> (#N)` and report done with the commit. A step SHALL end done in no other way.

#### Scenario: The agent writes the test and the code
- **WHEN** the model writes a test file and a source file, ticks the tasks of group 1, and ends its run, and the verification command, `ruff` and `mypy` exit 0
- **THEN** the step reports done, the checkout holds one new commit titled `The first group (#7)`, that commit holds the three files, and the tasks of group 1 are ticked in the commit

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

### Requirement: A step makes the only commit
The first exit check SHALL put `HEAD` back at the commit where the step started, or at the last `wip:` commit of the step, with `git reset --soft` when the agent moved it, so the checkout keeps the work of the agent and the later exit checks judge that work. The step SHALL stop with the class `head_moved` only when the reset exits with a status other than 0.

#### Scenario: A commit by the agent
- **WHEN** the agent commits its work with `git`, and ticks the tasks
- **THEN** the step resets `HEAD` to the commit where it started, prints one muted line that names the moved head and the expected head, and reports done with one commit whose parent is the commit where the step started and that holds the work of the agent

#### Scenario: A commit by the agent after a `wip:` commit
- **WHEN** the step made a `wip:` commit and the agent then makes its own commit in an extra turn
- **THEN** the step resets `HEAD` to the `wip:` commit, and the commit of the step folds the `wip:` commit and the work of the extra turn

#### Scenario: A failed check after the reset
- **WHEN** the agent commits its work and a later exit check fails
- **THEN** the step reports stopped with the reason of that check, not with the class `head_moved`, makes no commit, and the checkout is back at its last `wip:` commit, or at the commit where the step started when it made none

#### Scenario: A reset that fails
- **WHEN** the agent moved `HEAD` and `git reset --soft` to the expected head exits with a status other than 0
- **THEN** the step reports stopped with the class `head_moved`, and the reason names the reset command, its exit status and the output of git

### Requirement: A step refuses a checkout with uncommitted changes
The step SHALL refuse to start when `git status --porcelain` lists a change in the checkout, because a failed step resets the checkout. It SHALL raise `RoadmapImplementError` and make no model request.

#### Scenario: A dirty checkout
- **WHEN** the checkout holds an untracked file
- **THEN** the step raises `RoadmapImplementError` that names the checkout, the model gets no request, and the file stays

### Requirement: A fix step makes a failed check pass
The step SHALL accept a fix request: the name of a failed check and its log. The group of a fix step SHALL be "Make check `<name>` pass", with the verification commands of every group of the change. The inputs SHALL hold the log cut to `CONST_ROADMAP_IMPLEMENT_LOG_CHARS` characters from its end. The exit checks SHALL be those of a group, except that no task is ticked and `tasks.md` SHALL be as it was. A done fix step SHALL commit as `Make check <name> pass (#N)`.

#### Scenario: A fix step with a long log
- **WHEN** a fix request holds a log longer than the limit
- **THEN** the first message of the step holds the last characters of the log up to the limit, and the first characters are not in it

#### Scenario: The fix step ticks a task
- **WHEN** the model of a fix step ticks or edits a task in `tasks.md`, and changes a source file
- **THEN** the step reports done, and the commit holds the source file and `tasks.md` as it was

### Requirement: The job formats the changed Python files
Before the verification commands and the static checks, the step SHALL run `uv run ruff format` on the changed Python files, outside the shell of the agent, and stage the files it changed. The step SHALL print one line that names them. A formatter that fails SHALL stop the step. `ruff check` SHALL not fix. The step SHALL pass the file names after `--`, and SHALL stop on a symbolic link before it runs a tool.

#### Scenario: Correct code that is unformatted
- **WHEN** the model writes correct code that the formatter would change, ticks the tasks, and ends its run
- **THEN** the step reports done, the commit holds the formatted file, and the step prints one line that names the file

#### Scenario: Code that is formatted
- **WHEN** the formatter changes no file
- **THEN** the step prints no line about the format and reports done

#### Scenario: A lint or type error
- **WHEN** the code is unformatted and `ruff check` exits 1 after the format run
- **THEN** the step reports stopped with the reason that `ruff check` failed

#### Scenario: A file with a syntax error
- **WHEN** the formatter exits with status 2 on a changed file
- **THEN** the step reports stopped, the reason names the format command and its exit status, and the checkout is reset

#### Scenario: Only the changed files
- **WHEN** the model changes one Python file and one document
- **THEN** the format command names the Python file only

#### Scenario: A file named like an option
- **WHEN** a changed file has a name that starts with `-`
- **THEN** each tool gets the name after `--`, so the tool reads it as a path

#### Scenario: A symbolic link
- **WHEN** a changed Python file is a symbolic link
- **THEN** the step reports stopped, the reason names the link, and no formatter runs

### Requirement: The turn for a failed static check changes only the files of the step
The turn for a failed static check SHALL change no file except `tasks.md` and the files that the step had changed before the turn. The step SHALL check this with git, and SHALL stop with a reason that names the other paths when the turn changed any.

#### Scenario: The turn changes a file that the step did not change
- **WHEN** the model changes `src/other.py` in the extra turn, and the step had not changed it
- **THEN** the step reports stopped with the reason that names `src/other.py`, makes no commit and resets the checkout

#### Scenario: The turn changes a file that the step changed
- **WHEN** the model changes `src/sample.py` in the extra turn, and the step had changed it
- **THEN** the step checks all exit checks again and does not stop for the change

### Requirement: A step keeps the tests that existed
Every test that a `.py` file under `tests/` held at the commit where the step started SHALL be in the checkout after the run, by qualified name (`test_x` or `Class.test_x`), unless `recorded_tests` gives its `path::name`. A test is a function named `test_*`. When any other test is lost, the step SHALL stop with a reason that names the file and at most `CONST_ROADMAP_IMPLEMENT_REASON_TESTS` of its tests, and SHALL give no extra turn. A file that does not parse is skipped.

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
- **THEN** the step reports stopped, and the reason names the old file and `Check.test_a`

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
- **WHEN** the model removes `test_a`, and `recorded_tests` holds `tests/test_old.py::test_a`
- **THEN** the step reports done

#### Scenario: A rename or a move that the record names
- **WHEN** the model renames `test_a` to `test_z` or moves it to a new test file, and `recorded_tests` holds the old `path::name`
- **THEN** the step reports done

#### Scenario: A removal that the record does not name
- **WHEN** the model removes `test_a` and `test_b`, and `recorded_tests` holds only `tests/test_old.py::test_a`
- **THEN** the step reports stopped with the class `tests_lost`, and the reason names `test_b` and not `test_a`

#### Scenario: A kept task with a recorded removal
- **WHEN** the agent ticks a task whose verification passes, and the only test that it lost is in `recorded_tests`
- **THEN** the keeper makes the `wip:` commit

#### Scenario: The prompt of the step
- **WHEN** a test reads `roadmap_implement_step.md`
- **THEN** the rule of the tests names the `## Weakened checks` section, and says that an entry from the agent does not count

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
- **WHEN** a fix step runs and the model writes a new file under `tests/` that the plan names
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

### Requirement: The type check of a step is the type check of the gate
The step SHALL run `mypy` on the changed Python files under the paths of the type check of `devops ci`, with the options of that check. It SHALL take the paths and the options from the same definition as the row `typecheck` of `devops ci`. It SHALL run no type check on a changed file outside those paths, and no `mypy` when no changed file is inside them. It SHALL run `ruff check` and `ruff format` on every changed Python file.

#### Scenario: A test file with old type errors
- **WHEN** the model changes a test file that has type errors of its own, `mypy` would fail on that file, and the other exit checks pass
- **THEN** the step reports done, no `mypy` command ran, and `ruff check` ran on the test file

#### Scenario: A source file with a new type error
- **WHEN** the model changes a file under `src/` and a test file, and `mypy` fails on the source file
- **THEN** the command of `mypy` names only the source file, and the step runs its one extra turn with the text of the failure

#### Scenario: The step and the gate agree
- **WHEN** the step type-checks a file under each path of the gate
- **THEN** the command line of the step is the command line of the row `typecheck` with the files in place of the paths

### Requirement: The hooks of the repository are an exit check
After the static checks, the step SHALL run the `pre-commit` stage of the hooks over the staged changes. The child SHALL hold no GitHub token and SHALL have `PRE_COMMIT_HOME` under the data directory. The step SHALL install no git hook. The stage SHALL read the configuration that the job gives the step, a copy of the default branch, with `--config`. The step SHALL run no hook when the job gives it none.

#### Scenario: No hook configuration
- **WHEN** the repository holds no `.pre-commit-config.yaml` and the checks pass
- **THEN** the step reports done and runs no `pre-commit` command

#### Scenario: A configuration that the agent edits
- **WHEN** the agent writes `repos: []` to `.pre-commit-config.yaml`
- **THEN** every call of the stage names the copy of the configuration of the default branch with `--config`

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

#### Scenario: A stage that runs out of time
- **WHEN** the `pre-commit` stage runs out of time
- **THEN** the step reports stopped with a reason that says the command ran out of time, the model gets no extra turn, and the checkout is reset

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

### Requirement: A work-in-progress commit holds the tasks file of the job
The `wip:` commit SHALL hold the `tasks.md` as it was before the run with the ticks that the step verified, and no stray file of the group. The step SHALL make no `wip:` commit that would lose a test that existed at the start, unless the caller of the step gives its `path::name` in `recorded_tests`. The agent SHALL find its own `tasks.md` in the checkout after the commit.

#### Scenario: A test that the work would lose
- **WHEN** the model replaces a test file with a file that holds fewer of its tests, and ticks a task, and `recorded_tests` does not name the lost tests
- **THEN** the step runs no verification command at the tick and makes no `wip:` commit

#### Scenario: A stray file
- **WHEN** the model writes a file outside `src/`, `tests/`, `docs/` and `openspec/` and ticks a task
- **THEN** the `wip:` commit does not hold that file

### Requirement: A step that ends done folds its work in progress into its commit
A step that starts on a branch with `wip:` commits and ends done SHALL make one commit, titled `<group title> (#N)`, that holds all the work since the last commit that is no `wip:` commit. The branch SHALL then hold no `wip:` commit of that step. The exit checks SHALL judge all the work since that commit.

#### Scenario: A second step finishes the group
- **WHEN** a step stopped after a `wip:` commit, and a second step ticks the remaining task
- **THEN** the second step reports done, the message of its first request shows the kept task ticked, and the branch holds one new commit past the start, which does not start with `wip:`

### Requirement: A failure that no attempt can fix gets no repair round
A failure of the class `plan_defect` or `premise_false` SHALL get no repair round, whatever the setting `repair_rounds` is. The step SHALL stop with the evidence of the failure. Only a failed static check or hook gets a round.

#### Scenario: A group that changes no file
- **WHEN** the model ends its run and changes no file of a group
- **THEN** the step reports stopped with the class `plan_defect`, the model got one run and no extra turn, and the trace holds one attempt

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

### Requirement: A fix step changes only the paths that the plan names
A fix step SHALL stop with the class `outside_plan` when it changed, added or deleted a path that the plan does not name. The plan names a path in a code span of the text of any group of its `tasks.md`, which includes the `Reads:` line, the `Changes:` line and the tasks. A file under the change folder of the item is always allowed. The stop SHALL reset the checkout, SHALL name each path in its reason, and SHALL run no repair round. A group step SHALL NOT be subject to this rule.

#### Scenario: A fix step edits a path that the plan does not name
- **WHEN** a fix step writes `src/sample.py`, which the plan names, and `src/other.py`, which it does not
- **THEN** the step reports stopped with the class `outside_plan`, the reason names `src/other.py` and not `src/sample.py`, the diff holds the edit of `src/other.py`, no repair round ran, and the checkout is at its start commit

#### Scenario: A fix step adds an unnamed file
- **WHEN** a fix step writes a new file `tests/test_sample_fix.py` that the plan does not name
- **THEN** the step reports stopped with the class `outside_plan`

#### Scenario: A fix step deletes an unnamed file
- **WHEN** a fix step deletes `src/other.py`, which the plan does not name
- **THEN** the step reports stopped with the class `outside_plan`, and the file is back in the checkout

#### Scenario: A fix step edits only named paths and the change folder
- **WHEN** a fix step edits `src/sample.py`, which the plan names, and `design.md` of the change folder
- **THEN** the step ends done
