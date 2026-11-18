## ADDED Requirements

### Requirement: A line that names a module quotes a statement of that module
The stage plan check SHALL return a problem when a design decision, a rejected alternative or a `feasibility` line names a module under `src/` in a code span and no other code span of that line holds a statement of that module at the staged commit.

#### Scenario: A line that names a module with no statement is refused
- **WHEN** A `feasibility` line names `src/devops_cli/roadmap/step_files.py` and holds no second code span with a statement of that module
- **THEN** The check returns the module-quote problem for that line.

#### Scenario: A line that quotes its module is accepted
- **WHEN** A `feasibility` line names `src/devops_cli/roadmap/step_files.py` and holds `class TaskGroup:` in a second code span
- **THEN** The check returns no module-quote problem for that line.
