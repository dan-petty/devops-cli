## ADDED Requirements

### Requirement: A refused delivery title stops the item
The implement job SHALL run `title_problems` on the delivery title before it calls `create_draft_pull` and before it calls `update_pull`, and MUST stop the item when the check reports a problem.

#### Scenario: An edited title with no type stops the item
- **WHEN** A person edits the issue title to `Add a flag` after staging, so the delivery title has no Conventional Commit type.
- **THEN** The job stops the item before `create_draft_pull` and before `update_pull`, and the stop message names the title problem and the issue title.

#### Scenario: An undeclared type stops the item
- **WHEN** The issue title is `wip(cli): add a flag`, whose type the project does not declare.
- **THEN** The job stops the item with the reported problem and writes no pull request title.

#### Scenario: A declared title is written
- **WHEN** The issue title is `fix(cli): add a flag` and the `scope/cli` label is declared.
- **THEN** The job calls `create_draft_pull` or `update_pull` with the title `fix(cli): add a flag`.

#### Scenario: The first push leaves no branch without a pull request
- **WHEN** `_publish` has pushed the branch and `title_problems` reports a problem before `create_draft_pull`.
- **THEN** The job deletes the branch on `origin` and no draft pull request exists.
