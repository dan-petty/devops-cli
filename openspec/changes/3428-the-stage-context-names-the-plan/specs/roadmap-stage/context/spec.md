## ADDED Requirements

### Requirement: The stage context names the plan reader
The stage request context SHALL name `plan_read.read_change` with the path `src/devops_cli/roadmap/plan_read.py` and one line of purpose.

#### Scenario: The stage request holds the plan reader
- **WHEN** The stage job builds the model request for an item
- **THEN** The request context holds `plan_read.read_change`, the path `src/devops_cli/roadmap/plan_read.py` and one line of purpose.

### Requirement: The stage context names the revision reads
The stage request context SHALL name `plan_read.tree_files`, `plan_read.files_at` and `plan_read.change_root`, each with the path `src/devops_cli/roadmap/plan_read.py` and one line of purpose.

#### Scenario: The stage request holds the revision reads
- **WHEN** The stage job builds the model request for an item
- **THEN** The request context holds `plan_read.tree_files`, `plan_read.files_at` and `plan_read.change_root`, each with the path `src/devops_cli/roadmap/plan_read.py` and one line of purpose.

### Requirement: The stage context names the plan gate
The stage request context SHALL name `stage_change.check_proposal` with the path `src/devops_cli/roadmap/stage/stage_change.py` and one line of purpose.

#### Scenario: The stage request holds the plan gate
- **WHEN** The stage job builds the model request for an item
- **THEN** The request context holds `stage_change.check_proposal`, the path `src/devops_cli/roadmap/stage/stage_change.py` and one line of purpose.

### Requirement: The stage prompt names the existing plan reader
The stage prompt MUST tell the model to name `plan_read.read_change` when it plans a reader for a change folder, and MUST tell it to cite that reader instead of planning a second one.

#### Scenario: The planner prompt holds the reader rule
- **WHEN** The test loads the prompt `roadmap_stage_change.md`
- **THEN** The prompt text holds `plan_read.read_change` and the instruction to cite it instead of a second reader.
