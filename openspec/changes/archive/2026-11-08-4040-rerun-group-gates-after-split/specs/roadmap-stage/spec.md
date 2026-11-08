## ADDED Requirements

### Requirement: A split reply is judged by every gate of the first reply
The job SHALL judge the proposal that a split gives with the same call as the first reply, with the same arguments. A gate that finds a problem in the new groups SHALL send the reply back to the model with that problem, as it does for the first reply.

#### Scenario: A split changes a trigger path and runs no replay
- **WHEN** The first reply passes the gates, one group is over the budget, and the split gives a group that changes `src/devops_cli/roadmap/stage/stage_form.py` with no task that runs the replay of the stage job
- **THEN** the job sends the reply back with the problem of the `eval-replay` gate and makes three model calls

#### Scenario: A split drops a path of What Changes
- **WHEN** The first reply names a source file in What Changes and in a group, and the split gives groups that list that file nowhere
- **THEN** the job sends the reply back with the problem of the `what-changes` gate

#### Scenario: A split moves one module of a prefix
- **WHEN** The split gives a group that moves one module of a prefix to a subpackage and no group names the other module of the prefix in `changes`
- **THEN** the job sends the reply back with the problem of the `move-prefix` gate

#### Scenario: A split names a registry item and not its test module
- **WHEN** The split gives a group whose task names a registry item that a test module declares, and no task names the declared test module
- **THEN** the job sends the reply back with the problem of the `registry` gate
