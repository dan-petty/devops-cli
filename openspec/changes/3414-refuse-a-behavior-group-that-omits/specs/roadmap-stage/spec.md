## ADDED Requirements

### Requirement: Refuse a behavior group that omits the test of its module
The stage plan validation SHALL refuse a behavior group that changes an existing Python module under `src/` and names no test file of the staged tree that imports that module or carries the stem of the module in the test naming convention.

#### Scenario: A source change names only a new test
- **WHEN** a behavior group changes `src/devops_cli/roadmap/stage/stage_paths.py` and names only the test file it creates, while `tests/roadmap/stage/test_roadmap_stage_paths.py` imports that module
- **THEN** `existing_test_problems` returns one problem that names the group, the module and that test

### Requirement: Accept a behavior group that names the test of its module
The stage plan validation SHALL accept a behavior group that changes an existing Python module under `src/` and names at least one test file of the staged tree that imports that module or carries the stem of the module in the test naming convention.

#### Scenario: The named test imports the module and its file name differs from the module name
- **WHEN** a behavior group changes `src/devops_cli/roadmap/stage/stage_paths.py` and lists `tests/roadmap/stage/test_roadmap_stage_paths.py` in its `reads`
- **THEN** `existing_test_problems` returns no problem for that group

### Requirement: Exempt a module that has no existing test
The stage plan validation SHALL accept a behavior group that changes an existing Python module under `src/` when the staged tree holds no test file that imports that module and no test file that carries the stem of the module in the test naming convention.

#### Scenario: An existing module has no existing test
- **WHEN** a behavior group changes a module of `src/` and the staged tree holds no test file of that module
- **THEN** `existing_test_problems` returns no problem for that group

### Requirement: Leave out the test files that the plan creates
The stage plan validation MUST leave out every test path that a group lists in `creates`, so that a test file that the plan creates is no existing test.

#### Scenario: The plan creates the only test of a module it also changes
- **WHEN** a behavior group changes an existing module and creates the only test file that imports it
- **THEN** the created test is no existing test, and `existing_test_problems` returns no problem for that group

### Requirement: Report one problem for each group that omits its test
The stage plan validation SHALL report one problem for each behavior group that omits an existing test file of a module it changes.

#### Scenario: Two groups omit their existing tests
- **WHEN** two behavior groups each change an existing module of `src/` and name no existing test of it
- **THEN** `existing_test_problems` returns one problem for each group
