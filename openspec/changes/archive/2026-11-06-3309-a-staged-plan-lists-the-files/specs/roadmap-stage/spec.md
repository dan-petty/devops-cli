## ADDED Requirements

### Requirement: The comment lists the named paths that moved
The stage job SHALL list each path that a group of the plan names under `reads` or `changes` and that a commit on the default branch changed after the plan's base.

#### Scenario: A named plan path changes on main
- **WHEN** The plan names `src/devops_cli/roadmap/stage_change.py` under `reads` and a later commit on the default branch changes that file.
- **THEN** The comment of the staged item names `src/devops_cli/roadmap/stage_change.py` and the commit that changed it.

#### Scenario: An unnamed path changes on main
- **WHEN** A commit after the base changes a file that no group of the plan names under `reads` or `changes`.
- **THEN** The comment of the staged item does not name that file.

### Requirement: A moved path gives its commits in log order
The stage job SHALL give the short hash and the subject of each commit that changed a listed path, in log order.

#### Scenario: Two commits change one named path
- **WHEN** Two commits after the base change a path that the plan names under `changes`.
- **THEN** The comment lists the two short hashes and subjects under that path in log order.

#### Scenario: No commit changes a named path
- **WHEN** No commit after the base changes a path that the plan names under `reads` or `changes`.
- **THEN** The comment of the staged item has no moved-file section.

### Requirement: The comparison reads the latest default branch
The stage job MUST fetch the default branch before it compares the plan's base with the default branch.

#### Scenario: The remote default branch advances
- **WHEN** A remote commit changes a named path after the stage job fetched the base.
- **THEN** The comment of the staged item lists that path and commit.

### Requirement: The prompt asks for the preconditions of a called function
The stage prompt SHALL ask for one `feasibility` line for each called function whose arguments need a checkout, a client or a network.

#### Scenario: The stage prompt loads
- **WHEN** The stage job loads `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- **THEN** The prompt text names a checkout, a client and a network as preconditions to state in `feasibility`.
