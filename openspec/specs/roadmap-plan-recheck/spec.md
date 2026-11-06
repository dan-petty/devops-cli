# roadmap-plan-recheck Specification

## Purpose
How `devops roadmap plan-recheck` judges each change folder on the default branch again: the one result of a folder, the counts, and the promise that the command writes no file unless `--confirm` is given.

## Requirements

### Requirement: Plan-recheck gives each change folder one result
`devops roadmap plan-recheck` SHALL read each numbered folder of `openspec/changes/` on the default branch and give it one result: `ok`, `rewrite`, `new-plan`, `delivered` or `cleanup`.

#### Scenario: Each folder has one result
- **WHEN** the default branch holds three numbered change folders
- **THEN** the report holds three lines, and each line holds one result.

### Requirement: Plan-recheck leaves the folder of a closed issue out of every count
A folder whose issue is closed SHALL get the result `cleanup`, and no count of the report SHALL include it.

#### Scenario: A closed issue
- **WHEN** the default branch holds the folders of issue 1, which is open, and issue 2, which is closed
- **THEN** issue 2 gets `cleanup`, and the report counts one folder.

### Requirement: Plan-recheck marks a delivered plan
A folder SHALL get the result `delivered` when its plan marks files `(new)` and the default branch holds every one of them.

#### Scenario: The new file is on the default branch
- **WHEN** a plan marks `tests/test_sample.py` as new and the default branch holds that file
- **THEN** the folder gets `delivered`.

### Requirement: Plan-recheck reports a plan that fails a check
A folder that the plan reader refuses, or that fails `check_proposal` or `openspec validate`, SHALL get the result `new-plan`, with the first problem as its reason.

#### Scenario: A plan that does not read
- **WHEN** `tasks.md` of a folder holds no group
- **THEN** the folder gets `new-plan` and the reader error is its reason.

### Requirement: Plan-recheck reports a plan that a rewrite can fix
`devops roadmap plan-recheck` SHALL apply the mechanical rewrite to each live folder in memory and judge the rewritten plan with `read_change`, `check_proposal` and `openspec validate`. A folder SHALL get the result `rewrite` only when the rewrite changes it and the rewritten plan passes all three. A folder with no `Verification:` line SHALL count in the folders with no such line.

#### Scenario: A plan with no Verification line
- **WHEN** a plan has a group with no `Verification:` line and the group changes a test file
- **THEN** the folder gets `rewrite`, and the report counts it among the folders with no `Verification:` line.

### Requirement: Plan-recheck reports a plan that a rewrite does not fix
A folder that the rewrite does not fix SHALL get `new-plan`, with the first refusal of the rewritten plan as its reason.

#### Scenario: A plan that the rewrite does not fix
- **WHEN** a plan has a group with no `Verification:` line, and the group changes no test file and no document
- **THEN** the folder gets `new-plan`, and the reader error is its reason.

### Requirement: Plan-recheck writes nothing
The command SHALL write no file when `--confirm` is absent. With `--confirm` it SHALL write the rewritten files of the folders with the result `rewrite` to the working tree of the checkout that `--source` names. It SHALL make no write to git or to GitHub and SHALL call no model.

#### Scenario: A dry run
- **WHEN** a person runs `devops roadmap plan-recheck --dry-run`
- **THEN** the command prints the reads of a run and makes no request.

#### Scenario: A run without confirm
- **WHEN** a person runs `devops roadmap plan-recheck` on a plan that the rewrite changes
- **THEN** the report shows `rewrite` and the working tree holds no changed file.

#### Scenario: A run with confirm
- **WHEN** a person runs `devops roadmap plan-recheck --confirm --source <checkout>` on a plan that the rewrite changes
- **THEN** the files of the folder in the checkout hold the rewritten text, and `git status` shows them as changed and not committed.

### Requirement: Plan-recheck names the gate of each refusal
The plan-recheck report SHALL name the gate of each refusal. The gate is `read` for a folder that the plan reader refuses, `openspec` for a finding of `openspec validate`, or the name of one gate of `check_proposal`.

#### Scenario: A refusal carries its gate
- **WHEN** a plan names a file that no commit holds, and `check_proposal` refuses it
- **THEN** the line of the refusal holds the gate name `paths` and the message of the gate.

### Requirement: Plan-recheck compares a branch with the default branch
With the option `--branch <ref>`, plan-recheck SHALL read each change folder of the ref and of the default branch with the plan reader, judge both sets with the same gates, and call no model.

#### Scenario: Both sides are read
- **WHEN** the branch holds one change folder and the default branch holds two
- **THEN** the run reads three change folders with the plan reader and makes no model request.

### Requirement: Plan-recheck lists the refusals of each gate for both sides
With the option `--branch <ref>`, the plan-recheck report SHALL list the refusals of each gate for the branch and for the default branch.

#### Scenario: Each side lists its refusal under the gate
- **WHEN** one gate refuses one change folder on the branch and a different change folder on the default branch
- **THEN** the report lists both refusals under the name of that gate, each with its side.

### Requirement: A refusal that the branch adds is a case to review
With the option `--branch <ref>`, the plan-recheck report SHALL name the folder, the gate and the message of each refusal that the branch adds to the default-branch result, and SHALL mark each one as a case to review.

#### Scenario: A new refusal holds its three facts
- **WHEN** a change folder of the branch makes one gate refuse, and the default-branch result holds no such refusal
- **THEN** the report holds one line with the folder, the gate name, the message and the mark `case to review`.

### Requirement: A folder that the reader refuses does not stop a comparison
With the option `--branch <ref>`, plan-recheck SHALL report a change folder that the plan reader refuses as not read, and SHALL go on with the other folders.

#### Scenario: One folder of the branch does not read
- **WHEN** one change folder of the branch holds no task group and two other change folders read
- **THEN** the report names the unread folder as not read and holds the results of the two other folders.

### Requirement: The rewrite keeps the task groups
The mechanical rewrite SHALL keep every task group, its number, its title and its order, and SHALL change only the `Verification:` lines, the sample paths in task texts and the file `design.md`.

#### Scenario: The groups before and after
- **WHEN** a test parses a plan before and after the rewrite
- **THEN** each group has the same number, title and order, and only the lines that a rule names differ.

### Requirement: The rewrite adds a Verification line
The rewrite SHALL add one `Verification:` line under the first task of each group that has none. The command SHALL be `uv run devops ci test` with the test files of the `Changes:` line, or `uv run devops ci docs` when the group changes only documents. A behavior group SHALL get the `fails on the base` form. The rewrite SHALL NOT write a command that `read_verification` refuses.

#### Scenario: A group with a test file
- **WHEN** a group has no `Verification:` line and its `Changes:` line names `tests/test_sample.py`
- **THEN** the rewritten group has the line `Verification:` with the command `uv run devops ci test tests/test_sample.py`, and `read_verification` accepts the command.

### Requirement: The rewrite changes a sample path to a bare name
The rewrite SHALL change a path that a task text names to its bare file name when the tree lacks the path and no group lists or creates it.

#### Scenario: A sample path in a task
- **WHEN** a task names `tests/test_sample.py` in a code span, the tree lacks it, and no group lists it
- **THEN** the rewritten task names `test_sample.py`.

### Requirement: The rewrite adds a design stub
The rewrite SHALL add a `design.md` stub to a folder that has none, and `read_change` SHALL accept the folder.

#### Scenario: A folder with no design
- **WHEN** a change folder has no `design.md`
- **THEN** the rewrite adds `design.md`, and `read_change` reads the folder.

### Requirement: A write refuses a changed file
`devops roadmap plan-recheck --confirm` SHALL write no file when a file that it would change differs from the default branch in the working tree. It SHALL name that file.

#### Scenario: A local edit
- **WHEN** `tasks.md` of a `rewrite` folder has an uncommitted edit in the checkout
- **THEN** the command writes no file, exits with an error and names `tasks.md`.

### Requirement: A confirm run needs a checkout
`devops roadmap plan-recheck --confirm` SHALL stop with an error when `--source` is absent, and SHALL NOT write to the model clone.

#### Scenario: No source
- **WHEN** a person runs `devops roadmap plan-recheck --confirm` with no `--source`
- **THEN** the command exits with an error that names `--source` and writes no file.

### Requirement: A plan with no way forward leaves the implement queue
A Planned item whose merged plan fails `check_proposal` SHALL be left out of the implement job with the reason `implement_left_plan`, and `devops roadmap explain` SHALL name its first problem.

#### Scenario: A merged plan with a placeholder task
- **WHEN** the default branch holds the plan of a Planned item with the task `1.1 x`
- **THEN** `plan_implement` selects no target, and `explain_item` gives the reason that holds the first problem.
