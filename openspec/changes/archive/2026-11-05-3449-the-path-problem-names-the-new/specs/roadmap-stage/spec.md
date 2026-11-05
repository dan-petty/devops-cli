## ADDED Requirements

### Requirement: The missing-path message names both forms
The message of a path that the staged tree lacks SHALL name the `creates` list of a stage reply and the ` (new)` mark of the `Changes:` line of `tasks.md`.

#### Scenario: A group names a missing file
- **WHEN** `path_problems` judges a group that names `src/devops_cli/new_module.py` and no group creates it
- **THEN** the problem holds `creates`, ` (new)` and `Changes:`

#### Scenario: A plan omits the mark
- **WHEN** the plan check reads a change folder whose group 3 `Changes:` line names four new case files with no ` (new)` mark
- **THEN** each of the four problems holds ` (new)` and `Changes:`

### Requirement: The missing-path message keeps its hint
The missing-path message SHALL end with the hint that names the tracked files of the same name, or that states that no file has the name.

#### Scenario: A tracked file has the same name
- **WHEN** the tree holds `src/devops_cli/roadmap/stage.py` and a group names `src/devops_cli/new/stage.py`
- **THEN** the problem ends with the text of `stage_path_same_name` for `stage.py`

#### Scenario: A later group creates the path
- **WHEN** group 1 names `src/devops_cli/new_module.py` and group 3 lists it in `creates`
- **THEN** the problem names group 3 and holds neither `creates` nor ` (new)`

### Requirement: The module docstring names both readers
The module docstring of `stage_paths.py` SHALL state that `path_problems` judges both the stage reply and the change folder.

#### Scenario: A reader opens the module
- **WHEN** a test reads the module docstring of `src/devops_cli/roadmap/stage_paths.py`
- **THEN** the docstring holds `change folder` and `reply`
