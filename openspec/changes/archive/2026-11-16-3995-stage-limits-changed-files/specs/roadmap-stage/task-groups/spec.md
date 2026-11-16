## ADDED Requirements

### Requirement: Group file limit
The plan check SHALL refuse a task group that lists more than 5 paths in its `changes`, unless the group is a prefix move.

#### Scenario: A group over the limit
- **WHEN** `check_gates` judges a plan whose second group lists 6 paths in `changes` and is no prefix move.
- **THEN** The `group-files` gate holds one sentence for that group.

### Requirement: Group at the limit
The plan check SHALL accept a task group that lists 5 paths in its `changes`.

#### Scenario: A group at the limit
- **WHEN** `check_gates` judges a plan whose every group lists 5 paths in `changes`.
- **THEN** The `group-files` gate holds no sentence.

### Requirement: Prefix move exemption
The plan check SHALL accept a task group whose `changes` holds only the old modules of one prefix move and the modules that the group creates.

#### Scenario: A prefix move over the limit
- **WHEN** `check_gates` judges a plan whose group moves 5 modules and lists those 5 old paths and 5 new paths in `changes`.
- **THEN** The `group-files` gate holds no sentence.

### Requirement: Prefix move with an extra file
The plan check SHALL refuse a group that moves a prefix and also changes a path outside the move when the group lists more than 5 paths.

#### Scenario: A prefix move with an extra document
- **WHEN** `check_gates` judges a plan whose group moves 5 modules and also changes `docs/ROADMAP_WORKFLOW.md`.
- **THEN** The `group-files` gate holds one sentence for that group.

### Requirement: Refusal text
The refusal SHALL name the number of the group, its title and the number of paths that it changes.

#### Scenario: The refusal names the group
- **WHEN** A group titled `Wire the check` lists 6 paths in `changes` and is no prefix move.
- **THEN** The sentence holds `2`, `Wire the check` and `6`.

### Requirement: Split reply
A split reply SHALL obey the same file limit as the first reply.

#### Scenario: A split that keeps a large group
- **WHEN** The model's split reply holds a group that lists 6 paths in `changes` and is no prefix move.
- **THEN** The check returns one `group-files` sentence for that group.

### Requirement: Staging prompt
The staging prompt SHALL state the limit of 5 files in `Changes:`, the prefix-move exemption and the instruction to split a larger group.

#### Scenario: The prompt states the limit
- **WHEN** The stage task prompt renders.
- **THEN** It states the limit of 5 files, the prefix-move exemption and the split instruction.

### Requirement: Roadmap workflow document
The roadmap workflow document SHALL document the 5-file limit, the prefix-move exemption and the split instruction.

#### Scenario: The document states the limit
- **WHEN** A person reads the stage section of `docs/ROADMAP_WORKFLOW.md`.
- **THEN** It states the limit of 5 files, the prefix-move exemption and the split instruction.
