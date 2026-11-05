## Purpose
How `devops roadmap plan-recheck` judges each change folder on the default branch again: the one result of a folder, the counts, and the promise that the command writes nothing.

## ADDED Requirements

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
A folder that passes every check SHALL get the result `rewrite` when it has no `design.md` or no group has a `Verification:` line. A folder with no `Verification:` line SHALL count in the folders with no such line.

#### Scenario: A plan with no Verification line
- **WHEN** a plan passes every check and no group has a `Verification:` line
- **THEN** the folder gets `rewrite`, and the report counts it among the folders with no `Verification:` line.

### Requirement: Plan-recheck writes nothing
The command SHALL make no write to git or to GitHub and SHALL call no model.

#### Scenario: A dry run
- **WHEN** a person runs `devops roadmap plan-recheck --dry-run`
- **THEN** the command prints the reads of a run and makes no request.
