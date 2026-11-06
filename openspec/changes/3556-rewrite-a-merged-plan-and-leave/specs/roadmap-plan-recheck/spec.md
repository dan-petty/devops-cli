## MODIFIED Requirements

### Requirement: Plan-recheck reports a plan that a rewrite can fix
`devops roadmap plan-recheck` SHALL apply the mechanical rewrite to each live folder in memory and judge the rewritten plan with `read_change`, `check_proposal` and `openspec validate`. A folder SHALL get the result `rewrite` only when the rewrite changes it and the rewritten plan passes all three. A folder that the rewrite does not fix SHALL get `new-plan`, with the first refusal of the rewritten plan as its reason. A folder with no `Verification:` line SHALL count in the folders with no such line.

#### Scenario: A plan with no Verification line
- **WHEN** a plan has a group with no `Verification:` line and the group changes a test file
- **THEN** the folder gets `rewrite`, and the report counts it among the folders with no `Verification:` line.

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

## ADDED Requirements

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
