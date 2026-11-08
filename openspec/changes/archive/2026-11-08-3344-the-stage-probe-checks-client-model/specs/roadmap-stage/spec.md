## ADDED Requirements

### Requirement: A read of a model attribute that the model lacks is refused
The stage proposal check SHALL refuse a plan that names an attribute that the Pydantic model of the staged commit does not define, and SHALL name the reference and the module of the model in the problem.

#### Scenario: PullStatus lacks labels
- **WHEN** A plan names `PullStatus.labels`, and the recorded `PullStatus` of `src/devops_cli/github/client.py` defines no `labels` field.
- **THEN** `check_proposal` returns a problem that names `PullStatus.labels` and `src/devops_cli/github/client.py`.

#### Scenario: A model field that exists passes
- **WHEN** A plan names `PullStatus.state`, and the recorded `PullStatus` of `src/devops_cli/github/client.py` defines `state`.
- **THEN** `check_proposal` returns no problem for that reference.

#### Scenario: A name that is no model class is left alone
- **WHEN** A plan names `stage_ready.item`, and no Pydantic model class of the staged commit is named `stage_ready`.
- **THEN** `check_proposal` returns no problem for that reference.

#### Scenario: A caller gives no model map
- **WHEN** `check_proposal` runs with no `models` argument on a plan that names `PullStatus.labels`.
- **THEN** `check_proposal` returns no problem for that reference.

### Requirement: The module of a model that a plan extends is in changes
The stage proposal check SHALL return a problem that names the module of a model when a plan reads an attribute that the model lacks and no group lists that module in `changes`, and SHALL return no such problem when a group lists it.

#### Scenario: The plan omits the model module
- **WHEN** A plan reads `PullStatus.labels` and no group lists `src/devops_cli/github/client.py` in `changes`.
- **THEN** `check_proposal` returns a problem that tells the model to add `src/devops_cli/github/client.py` to a group's `changes`.

#### Scenario: The plan lists the model module
- **WHEN** A plan reads `PullStatus.labels` and a group lists `src/devops_cli/github/client.py` in `changes`.
- **THEN** `check_proposal` returns no problem for the model attribute.

#### Scenario: A second reply with the same gap stops the item
- **WHEN** The first and the second reply both read `PullStatus.labels` and both omit `src/devops_cli/github/client.py` from `changes`.
- **THEN** The stage job records a failure of the item with `RoadmapStageError`, and the plan holds no ready change.
