## ADDED Requirements

### Requirement: A move needs the module in another place
The stage job SHALL treat a Python module as moved only when a task group lists it in `changes` and creates, in `creates`, a module of the same name or a module under the sub-package that the name prefix of the module gives. A group that creates only a test, a document or a module of another name SHALL move no module, and the job SHALL probe no reference for it.

#### Scenario: A group edits a module and creates a test
- **WHEN** a group lists `src/devops_cli/roadmap/stage_probe.py` in `changes` and creates `tests/roadmap/test_stage_probe.py`.
- **THEN** the group moves no module.

#### Scenario: A group moves a module into a sub-package
- **WHEN** a group lists `src/devops_cli/roadmap/stage_probe.py` in `changes` and creates `src/devops_cli/roadmap/stage/probe.py`.
- **THEN** the group moves `src/devops_cli/roadmap/stage_probe.py`, with the dotted name `devops_cli.roadmap.stage_probe`.

### Requirement: A reference in a file of a tool or a record needs no task group
The stage job SHALL accept a probed reference to a moved module with no task group and no `unchanged` entry when the file is of class `tool-owned` or `record` in the inventory of the documents. It SHALL refuse any other probed file that no group changes and that the reply does not mark unchanged.

#### Scenario: The changelog names a moved module
- **WHEN** the probe lists `CHANGELOG.md`, and no group changes it.
- **THEN** `check_proposal` returns no problem for `CHANGELOG.md`.

#### Scenario: The folder of another change names a moved module
- **WHEN** the probe lists `openspec/changes/3253-map-all-issue-requirements-to-a/proposal.md`, and no group changes it.
- **THEN** `check_proposal` returns no problem for that path.

#### Scenario: A hand-written document names a moved module
- **WHEN** the probe lists `docs/ROADMAP_WORKFLOW.md`, and no group changes it.
- **THEN** `check_proposal` returns a problem that names `docs/ROADMAP_WORKFLOW.md`.
