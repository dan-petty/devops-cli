# roadmap-eval-implement Specification

## Purpose
How `devops roadmap eval implement` measures the implement job: fixtures of real items with the properties of a good result, one step run in a scratch clone with a chosen model, and a report by property, so that a change to the prompt or the tools of the job states a score before and after.

## ADDED Requirements

### Requirement: A fixture is a folder with a case, an issue, a plan and its results
A fixture SHALL be a folder under `tests/fixtures/roadmap_eval/implement/` with `case.json`, `issue.md`, the plan files in `plan/`, and the diffs of its recorded results in `results/`. The loader SHALL refuse a fixture that breaks the schema or contradicts its own plan, and SHALL raise `ImplementEvalError` that names the fixture.

#### Scenario: A valid fixture
- **WHEN** the loader reads a fixture folder with all its files
- **THEN** it returns the case with the issue text, the plan files and the diffs

#### Scenario: A path that the plan does not name
- **WHEN** `changes` of a fixture lists a path that no code span of the group holds
- **THEN** the loader raises `ImplementEvalError` and names the fixture and the path

#### Scenario: A recorded result without a diff file
- **WHEN** `case.json` names a result whose diff file is not in `results/`
- **THEN** the loader raises `ImplementEvalError` and names the file

#### Scenario: A field the schema lacks, a bad SHA or a missing group
- **WHEN** `case.json` holds an unknown field, a base that is no 40-character SHA, or a group that the plan lacks
- **THEN** the loader raises `ImplementEvalError`

#### Scenario: A result that expects a command property to fail
- **WHEN** a recorded result expects `tests_pass` to fail
- **THEN** the loader accepts it, and a check with commands compares that property

### Requirement: The committed set holds both good and bad results
The committed set SHALL hold at least 10 fixtures, the fixtures of #2175 and #2735 among them. It SHALL hold a recorded result that fails no property and a recorded result that fails some.

#### Scenario: The committed set
- **WHEN** the loader reads the committed folder
- **THEN** it returns at least 10 fixtures, including those of #2175 and #2735, with a recorded result that fails no property and one that fails some

### Requirement: The property tests_kept finds a lost or weakened test
`tests_kept` SHALL fail when the diff deletes a Python file under `tests/`, removes a test name that no added line of the same file defines, takes assertion lines from a test on balance, or adds a skip or xfail to a test whose `def` stays, unless the fixture allows that `path::name`.

#### Scenario: A deleted test
- **WHEN** the diff deletes `tests/test_sample.py`, which defined `test_a`
- **THEN** `tests_kept` fails and names `tests/test_sample.py::test_a`

#### Scenario: A test that moves in its file
- **WHEN** the diff removes `def test_a` from one place of a test file and adds it at another place of the same file
- **THEN** `tests_kept` passes

#### Scenario: A deletion item that allows a lost test
- **WHEN** the diff removes `test_dead` and the fixture allows `tests/test_sample.py::test_dead`
- **THEN** `tests_kept` passes

#### Scenario: A test that becomes a stub
- **WHEN** the diff replaces the assertion lines of `test_y` with `pass`, or removes `test_y` and adds a `test_y` with no assertion
- **THEN** `tests_kept` fails and names `tests/test_sample.py::test_y` as weakened

#### Scenario: A skip on an existing test
- **WHEN** the diff adds `@pytest.mark.skip` above a `test_y` that already exists
- **THEN** `tests_kept` fails and names `tests/test_sample.py::test_y` as weakened

### Requirement: The property diff_scope finds a path outside the group
`diff_scope` SHALL fail when the diff touches a path other than the `changes` paths of the fixture and the `tasks.md` of its change.

#### Scenario: A path outside the group
- **WHEN** the diff touches `src/other.py` and the `changes` paths list `src/sample.py`
- **THEN** `diff_scope` fails and names `src/other.py`

#### Scenario: The tasks file
- **WHEN** the diff touches only a path of `changes` and the `tasks.md` of the change
- **THEN** `diff_scope` passes

### Requirement: The property no_scratch finds a scratch file
`no_scratch` SHALL fail when the diff adds a file at the root of the repository, under `.data/`, or with the suffix `.bak`, `.orig`, `.rej` or `.tmp`, unless the `changes` paths name that file.

#### Scenario: A scratch file
- **WHEN** the diff adds `tmp_test.py` at the root
- **THEN** `no_scratch` fails and names `tmp_test.py`, and `diff_scope` fails too

#### Scenario: A new file the group names
- **WHEN** the diff adds `tests/test_new.py` and `changes` lists it
- **THEN** `no_scratch` passes

### Requirement: The property tasks_ticked reads the ticks the diff gives
`tasks_ticked` SHALL apply the hunks of the diff for the `tasks.md` of the change to the plan text, and SHALL fail unless every task of the group is ticked in the result. It SHALL fail when a hunk does not match the plan text.

#### Scenario: Every task ticked
- **WHEN** the diff changes every `- [ ]` of the group in `tasks.md` to `- [x]`
- **THEN** `tasks_ticked` passes

#### Scenario: One task ticked
- **WHEN** the diff ticks one of two tasks
- **THEN** `tasks_ticked` fails and names the unticked task

### Requirement: A cut diff leaves the four diff properties skipped
When the step stopped and `StepOutcome.diff_cut` is set, the four properties that read the diff SHALL be skipped with the reason that the diff is cut.

#### Scenario: A cut diff
- **WHEN** the step was stopped and its diff is cut
- **THEN** the four properties are skipped, with the reason that the diff is cut

### Requirement: Two properties run commands in the tree of the result
`tests_pass` SHALL run each command of `tests_pass` of the fixture, and `verify_passes` SHALL run each verification command of the group, in the tree of the result. A property SHALL pass when every command exits 0. A command whose program is not on the allowlist of the step SHALL fail the property. A step that stopped has no tree, so both properties are skipped with the reason of the stop.

#### Scenario: A failing command
- **WHEN** a named command exits 1
- **THEN** `tests_pass` fails and its detail names the command and the end of its output

#### Scenario: A stopped step
- **WHEN** the step stops on a failed check
- **THEN** `tests_pass` and `verify_passes` are skipped and name the reason of the stop

### Requirement: A run executes one step in a scratch clone and touches no GitHub state
For each fixture, the command SHALL clone the checkout at the base SHA into a temporary folder, remove the remote, write the plan folder and commit it, and run the group through `run_step` with the chosen model and the item from the fixture. It SHALL then evaluate the six properties, and SHALL remove the folder. It SHALL send no request to GitHub, push nothing, and leave the checkout it cloned from as it was.

#### Scenario: A step that does the group
- **WHEN** the model writes the files of the group and ticks its tasks, and the commands exit 0
- **THEN** the report shows the step done, and every property passes

#### Scenario: A step that makes a scratch file
- **WHEN** the model writes `scratch.py` at the root and the step stops on a failed static check
- **THEN** the report shows the step stopped with its reason, and `no_scratch` and `diff_scope` fail on the diff that the step kept

#### Scenario: Nothing is left
- **WHEN** a run ends
- **THEN** the temporary folder is gone, the source checkout has the same commit and no new file, and the roadmap store saw no read

### Requirement: The report lists the cost and the failed property
The report SHALL list, for each fixture, the status of the step, each property as pass, fail or skipped with its detail, the input and output tokens, the requests, the tool calls, the wall time in seconds, and the first property that failed. `--json` SHALL print the same fields as JSON. A run SHALL write the JSON report under `eval/implement/` of the data directory, in a new file for each run, and SHALL do so also when a fixture raises, for the fixtures before it.

#### Scenario: The table
- **WHEN** a run covers two fixtures and one fails `diff_scope`
- **THEN** the output has a block for each, the failed block names `diff_scope` and its detail, and the last line counts the properties that passed

#### Scenario: A fixture that raises
- **WHEN** the second fixture of a run raises an error
- **THEN** the report of the first fixture is printed and written, and the command exits with the error

#### Scenario: Two runs in the same second
- **WHEN** two reports are written in the same second
- **THEN** each report has its own file

#### Scenario: The JSON report
- **WHEN** a run ends
- **THEN** a file under `eval/implement/` of the data directory holds the model, the fixtures and the fields above

### Requirement: A check of recorded results needs no model
With `--check-only`, the command SHALL evaluate the four properties of each recorded result of each chosen fixture, make no model call, and make no clone. It SHALL exit 1 when the properties that fail differ from the properties the fixture expects to fail. With `--run-commands` it SHALL also clone, apply the diff, evaluate the two properties that run commands, and compare all six with the record.

#### Scenario: Every recorded result behaves as recorded
- **WHEN** the committed fixtures are checked with `--check-only`
- **THEN** the exit code is 0 and no model call is made

#### Scenario: A command property that differs from the record
- **WHEN** `--run-commands` runs and `tests_pass` fails for a result whose record does not expect it
- **THEN** the command exits 1

#### Scenario: A result that does not behave as recorded
- **WHEN** a fixture expects a result to fail `diff_scope` and the diff touches only allowed paths
- **THEN** the command exits 1 and names the fixture, the result and the property

### Requirement: A dry run lists the steps and makes no request
With `--dry-run`, the command SHALL list each chosen fixture with its issue, group and base SHA, and the model request of each step, and SHALL make no request, clone nothing and call no model. The command SHALL refuse a name for `--fixture` that no fixture has.

#### Scenario: A dry run
- **WHEN** `devops roadmap eval implement --dry-run` runs
- **THEN** it lists every fixture and one model request for each, and the model gets no request

#### Scenario: An unknown fixture
- **WHEN** `--fixture` names a folder that does not exist
- **THEN** the command exits 1 and lists the known names
