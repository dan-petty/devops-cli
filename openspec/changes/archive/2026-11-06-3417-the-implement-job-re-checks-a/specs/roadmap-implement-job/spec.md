## ADDED Requirements

### Requirement: The job checks the premise of a behavior group at the branch tip
Before the job runs a behavior group, the job SHALL check each guard or check identifier that a task of the group adds against the branch tip, and SHALL return the item to New with the definition line when the branch tip defines it. The job SHALL read the kind of the group from `TaskGroup.is_behavior` of `src/devops_cli/roadmap/step_files.py`.

#### Scenario: A task adds a guard that the base already runs
- **WHEN** A behavior group task says to add the guard `_delivery_title` and the branch tip defines `_delivery_title`
- **THEN** The job runs no group step, writes no group file, makes no group commit, and comments the definition line with the return to New.

#### Scenario: A task adds a guard that the base lacks
- **WHEN** A behavior group task says to add the guard `_missing_guard` and the branch tip defines no `_missing_guard`
- **THEN** The job runs the group and commits the file that the group writes.

#### Scenario: A group that is not behavior adds a defined name
- **WHEN** A group whose kind is not behavior has a task that says to add the name `_delivery_title`, which the branch tip defines
- **THEN** The job returns no item to New and runs the group.

### Requirement: One shared definition lookup reports a definition at a commit
The stage job and the implement job SHALL use the definition lookup of `src/devops_cli/roadmap/premise.py`: `definition_lines` returns the lines that define an identifier at a commit, and `defines` reports whether that list is not empty.

#### Scenario: Both jobs get the definition lines from one function
- **WHEN** The stage job probes a cited identifier and the implement job checks a task at the same commit
- **THEN** Both jobs get the same definition lines from `definition_lines` of `src/devops_cli/roadmap/premise.py`.

#### Scenario: The check writes nothing
- **WHEN** The implement job checks the tasks of a behavior group at the branch tip
- **THEN** The check runs only read-only git commands and the worktree holds no change.
