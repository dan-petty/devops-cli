## ADDED Requirements

### Requirement: A task group writes no file under openspec/changes
A `StageGroup` SHALL reject a path in `changes` or `creates` that is `openspec/changes` or that starts with `openspec/changes/`, and SHALL accept such a path in `reads`.

#### Scenario: A change-folder path in changes
- **WHEN** a `StageGroup` sets `changes` to `openspec/changes/3060-model-tier-ladder/proposal.md`
- **THEN** validation fails with a message that names that path and the rule

#### Scenario: A change-folder path in creates
- **WHEN** a `StageGroup` sets `creates` and `changes` to `openspec/changes/3060-model-tier-ladder/tasks.md`
- **THEN** validation fails with a message that names that path

#### Scenario: The change folder itself
- **WHEN** a `StageGroup` sets `changes` to `openspec/changes`
- **THEN** validation fails

#### Scenario: A change-folder path in reads
- **WHEN** a `StageGroup` sets `reads` to `openspec/changes/3060-model-tier-ladder/proposal.md` and changes `src/devops_cli/roadmap/stage_change.py`
- **THEN** validation succeeds

### Requirement: The path check reports a change-folder path
`path_problems` SHALL report a group path that is `openspec/changes` or that starts with `openspec/changes/`, in the place where the group names it, so that `check_proposal` refuses a recorded plan that skipped the schema.

#### Scenario: A recorded group that creates a change file
- **WHEN** `path_problems` runs on a group built without validation that creates `openspec/changes/3060-model-tier-ladder/proposal.md`
- **THEN** it returns one problem that names the group, the path and the rule

#### Scenario: A recorded group that only reads a change file
- **WHEN** `path_problems` runs on a group that reads `openspec/changes/3060-model-tier-ladder/proposal.md` in a tree that holds that file
- **THEN** it returns no problem

### Requirement: The stage prompt forbids a change-folder write
The roadmap stage prompt SHALL state that an implementation group must not change or create a path under `openspec/changes/`.

#### Scenario: The prompt states the rule
- **WHEN** the prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` is read
- **THEN** it holds a sentence that names `openspec/changes/` and forbids the change and the creation of a path under it
