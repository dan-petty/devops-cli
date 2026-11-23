## ADDED Requirements

### Requirement: A branch run fails on a folder that the branch changes
With `--branch`, `devops roadmap plan-recheck` SHALL exit 1 when a change folder that the branch adds or changes, against the default branch, has a result other than `ok`, and SHALL print one line for each such folder. A refusal of a folder that the branch does not change SHALL not change the exit code.

#### Scenario: A plan branch with a refused folder
- **WHEN** a branch adds a change folder that a gate refuses, and the command runs with `--branch` and that branch
- **THEN** the command prints the folder and exits 1

#### Scenario: The branch of a new gate
- **WHEN** a branch changes only source code, and the new gate on the branch refuses two folders of the default branch
- **THEN** the command lists the two refusals as new refusals and exits 0

### Requirement: The recheck reads the issues from a listing file
With `--issues <file>`, `devops roadmap plan-recheck` SHALL read the open issues and the closed issues from the file, a list of `IssueRecord`, and SHALL send no GitHub request.

#### Scenario: A run with a listing file
- **WHEN** the command runs with `--issues` and a store factory that raises on any call
- **THEN** the command gives each folder the result that a run with the store gives, and the factory gets no call
