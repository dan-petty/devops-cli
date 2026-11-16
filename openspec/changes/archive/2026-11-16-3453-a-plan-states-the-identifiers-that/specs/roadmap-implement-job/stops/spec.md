## MODIFIED Requirements

### Requirement: The job checks the premise of a behavior group at the branch tip
Before the job runs a behavior group, the job SHALL read the identifiers of the `Adds:` line of the group through `TaskGroup.added_names` of `src/devops_cli/roadmap/step_files.py`, and SHALL return the item to New with the definition line when the branch tip defines one of them. The job SHALL use no rule of a task text. The job SHALL read the kind of the group from `TaskGroup.is_behavior` of `src/devops_cli/roadmap/step_files.py`, and a group of another kind SHALL run with no check.

#### Scenario: A task adds a guard that the base already runs
- **WHEN** A behavior group holds an `Adds:` line with `_delivery_title`, and the branch tip defines `_delivery_title`
- **THEN** The job runs no group step, writes no group file, makes no group commit, and comments the definition line with the return to New.

#### Scenario: A task adds a guard that the base lacks
- **WHEN** A behavior group holds an `Adds:` line with `_missing_guard`, and the branch tip defines no `_missing_guard`
- **THEN** The job runs the group and commits the file that the group writes.

#### Scenario: A task names a defined guard and the group has no Adds line
- **WHEN** A behavior group task says to add a check beside the guard `_delivery_title`, which the branch tip defines, and the group holds no `Adds:` line
- **THEN** The job returns no item to New and runs the group.

#### Scenario: A group that is not behavior adds a defined name
- **WHEN** A group whose kind is not behavior names the guard `_delivery_title`, which the branch tip defines, and holds no `Adds:` line
- **THEN** The job returns no item to New and runs the group.

#### Scenario: The guard premise fails after a checkpoint
- **WHEN** groups 1 and 2 passed and were pushed as checkpoints, and the `Adds:` line of a behavior group 3 names a guard that the branch tip defines
- **THEN** the job runs no step for group 3, withdraws the checkpoints as for a `premise` request, and returns the item to New
