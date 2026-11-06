# roadmap-plan-recheck Specification

## Purpose
How `devops roadmap plan-recheck` judges each change folder on the default branch again: the one result of a folder, the counts, and the promise that the command writes nothing.

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
A folder that passes every check SHALL get the result `rewrite` when it has no `design.md` or no group has a `Verification:` line. A folder with no `Verification:` line SHALL count in the folders with no such line.

#### Scenario: A plan with no Verification line
- **WHEN** a plan passes every check and no group has a `Verification:` line
- **THEN** the folder gets `rewrite`, and the report counts it among the folders with no `Verification:` line.

### Requirement: Plan-recheck writes nothing
The command SHALL make no write to git or to GitHub and SHALL call no model.

#### Scenario: A dry run
- **WHEN** a person runs `devops roadmap plan-recheck --dry-run`
- **THEN** the command prints the reads of a run and makes no request.

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
