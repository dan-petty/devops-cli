# roadmap-project-dependencies Specification

## Purpose
What the roadmap jobs do in a managed repository that lacks a project-management dependency, such as `openspec/config.yaml`, and how a row of the Service records the missing dependency so that onboarding can add it.

## Requirements

### Requirement: The stage job holds the items of a repository without OpenSpec
The stage job SHALL leave out every item of a repository whose default branch holds no `openspec/config.yaml`, also an item that `--item` names. For such a repository it SHALL push no branch and call no model. The reason SHALL name the file and say that onboarding adds it.

#### Scenario: A round in a repository without the file
- **WHEN** the default branch holds no `openspec/config.yaml` and the stage row of the Service runs with one Ready item
- **THEN** `origin` holds no new branch, the model gets no call, the counter counts the item as skipped with the reason `no_openspec`, and the log line of the item names the file

#### Scenario: A named item in a repository without the file
- **WHEN** the default branch holds no `openspec/config.yaml` and the command runs with `--item N` for a Ready item
- **THEN** the plan stages no item and leaves out item N with the reason that names the file

#### Scenario: Explain names the hold
- **WHEN** `devops roadmap explain N` runs for a Ready item of a repository whose default branch holds no `openspec/config.yaml`
- **THEN** the stage verdict is no, with the reason that names the file

### Requirement: The stage row records the missing file for onboarding
The outcome of the stage row SHALL name each project file that the default branch lacks, so that a later row of the round can start the onboarding of the repository. A repository whose default branch holds `openspec/config.yaml` SHALL get the selection and the plan it got before, and an outcome that names no file.

#### Scenario: The outcome names the file
- **WHEN** the stage row runs in a repository whose default branch holds no `openspec/config.yaml`
- **THEN** the outcome of the row names `openspec/config.yaml`, and the report of the plan prints the reason

#### Scenario: A repository with OpenSpec
- **WHEN** the default branch holds `openspec/config.yaml`
- **THEN** the plan and the outcome name no missing file, and the report holds no line about the file
