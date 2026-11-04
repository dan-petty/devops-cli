## ADDED Requirements

### Requirement: Refuse a What Changes path that no group lists
The proposal check SHALL return a problem when a repository path in a code span of a What Changes item is in neither the changes nor the creates list of any task group.

#### Scenario: What Changes names a path that no group lists
- **WHEN** A proposal has a What Changes item with the code span `src/devops_cli/lang/en/messages.py`, and no group lists that path in `changes` or `creates`
- **THEN** `check_proposal` returns a problem that names the unlisted path

#### Scenario: What Changes names a path that a group changes
- **WHEN** A proposal has a What Changes item with the code span `src/devops_cli/roadmap/stage_change.py`, and a group lists that path in `changes`
- **THEN** `check_proposal` returns no problem for that path

#### Scenario: What Changes names a path that a group creates
- **WHEN** A proposal has a What Changes item with the code span `src/devops_cli/roadmap/new_check.py`, and a group lists that path in `creates`
- **THEN** `check_proposal` returns no problem for that path

### Requirement: Ignore a What Changes item with no unlisted path
The proposal check SHALL accept a What Changes item when it holds no repository path in a code span, or when each code span that is a repository path is listed by a task group.

#### Scenario: What Changes item describes behaviour only
- **WHEN** A proposal has a What Changes item with no code span that is a repository path
- **THEN** `check_proposal` returns no problem for that item

#### Scenario: What Changes names a command in a code span
- **WHEN** A proposal has a What Changes item with the code span `uv run devops ci test`
- **THEN** `check_proposal` returns no problem for that code span

#### Scenario: The replay runs the What Changes check on a reply alone
- **WHEN** The replay calls `check_proposal` with a proposal and no checkout
- **THEN** The replay returns the unlisted-path problem and makes no git call
