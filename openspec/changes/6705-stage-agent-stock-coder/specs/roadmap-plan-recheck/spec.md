## ADDED Requirements

### Requirement: A run with a base judges the folders that the branch changes
With `--branch <ref>` and `--base <sha>`, `devops roadmap plan-recheck` SHALL make no fetch and SHALL read no ref of the default branch. It SHALL judge each change folder that `git diff --name-only <sha>..<ref>` names, on the tree of the ref. The command SHALL exit 1 when one of these folders is not `ok`.

#### Scenario: An origin that refuses each fetch
- **WHEN** the `origin` of the clone is a path that does not exist, and the command runs with `--base`
- **THEN** the command judges the folder of the branch and sends no fetch

#### Scenario: A repository with no origin HEAD
- **WHEN** the recheck runs with a base and the default branch, in a new repository that fetched only the base and applied the patch
- **THEN** the recheck judges the folder of the branch and reads no ref of `origin`

#### Scenario: The JSON of a failed folder
- **WHEN** the command runs with `--base` and `--json`, and the folder of the branch is refused
- **THEN** the JSON lists the folder in the failed folders of the branch, and the command prints no other line and exits 1

### Requirement: A run with a base adds the rules of the stage plan
With `--base`, the judge of a folder SHALL add `staged_problems` and the test references of the removal scan. With `--candidate <file>`, `staged_problems` SHALL judge the title and the body that the stage builder makes from the file.

#### Scenario: A plan branch with a group over the budget
- **WHEN** a branch adds a change folder whose group is over the step budget, and the command runs with `--branch` and `--base`
- **THEN** the command names the folder and the rule `group-over-budget`, and exits 1

#### Scenario: A candidate with a closing keyword
- **WHEN** the candidate holds a closing keyword before a reference to another issue, and the command runs with `--base` and `--candidate`
- **THEN** the command names the closing keyword and exits 1

### Requirement: The recheck reads the issues from a listing file
With `--issues <file>`, `devops roadmap plan-recheck` SHALL read the issues from the file, a list of `IssueRecord`, and SHALL open no store. Its dry run SHALL list no issue read, and with `--base` no fetch.

#### Scenario: A run with a listing file
- **WHEN** the command runs with `--issues` and a store factory that raises on any call
- **THEN** the command gives the folder the result that a run with the store gives, and the factory gets no call
