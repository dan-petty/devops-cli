## ADDED Requirements

### Requirement: The stop of an ahead clone names the commit that it kept
When the clone's HEAD differs from the staged commit after the fast-forward merge, `_move_clone` SHALL raise `GitOperationError`, and the `stage_clone_ahead` message SHALL name the staged commit, the short hash of the clone's HEAD and the subject of its commit. A clone that is behind the staged commit SHALL reach it with no error.

#### Scenario: A clone ahead of the staged commit
- **WHEN** the clone's HEAD holds a local commit that the staged commit does not, and `git merge --ff-only` reports it up to date
- **THEN** `_move_clone` raises `GitOperationError` with the staged commit, the short hash and the subject of the local commit, and the clone keeps its HEAD

#### Scenario: A clone behind the staged commit
- **WHEN** the clone's HEAD is an ancestor of the staged commit
- **THEN** `git rev-parse HEAD` in the clone returns the staged commit, and `_move_clone` returns with no error
