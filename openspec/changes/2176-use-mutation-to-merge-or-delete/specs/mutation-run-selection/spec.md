## Purpose
How the mutation run selects the tests it runs inside its copy of the tree, so that a stats run completes on this tree and names only test paths that a file of this tree holds.

## ADDED Requirements

### Requirement: The mutation selection names test paths of this tree
The mutation run MUST select only test paths that a file of this tree holds.

#### Scenario: A selection path that no file holds
- **WHEN** the mutation test selection names a path that no file of this tree holds
- **THEN** the selection check fails and names that path

#### Scenario: Every selection path holds a test
- **WHEN** every path of the mutation test selection is a file of this tree
- **THEN** the selection check passes with no finding

### Requirement: The mutation run copies the living specs
The mutation run MUST copy the living specs folder into the tree that it runs the tests in, because a test of that tree reads a spec of the living specs.

#### Scenario: A copy list that holds the living specs
- **WHEN** the mutation copy list of the project manifest names the living specs folder
- **THEN** the selection check reports no finding

#### Scenario: A copy list that drops the living specs
- **WHEN** the mutation copy list holds no living specs folder
- **THEN** the selection check fails and names the copy list
