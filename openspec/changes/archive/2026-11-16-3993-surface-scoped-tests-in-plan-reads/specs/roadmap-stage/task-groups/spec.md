## ADDED Requirements

### Requirement: Scoped tests in plan reads
When stage plans a task group, it SHALL run `plan_tests()` against the group's planned `Changes:` list and add each selected test module to the group's `Reads:` list.

#### Scenario: Source change selects a test
- **WHEN** Stage plans a group whose `Changes:` list contains a source file that `plan_tests()` maps to a test module.
- **THEN** The group's `Reads:` list contains that test module.

### Requirement: Existing reads preserved
Stage MUST keep every file that it already puts in a group's `Reads:` list and MUST add each scoped test module once.

#### Scenario: Scoped test is already in reads
- **WHEN** A test module selected by `plan_tests()` is already in the group's `Reads:` list.
- **THEN** The group's `Reads:` list contains that module once and keeps the other files.

### Requirement: No scoped tests
When `plan_tests()` returns no test module for a group, stage MUST leave the group's `Reads:` list unchanged.

#### Scenario: No test covers the change
- **WHEN** Stage plans a group whose `Changes:` list yields no test module from `plan_tests()`.
- **THEN** The group's `Reads:` list has the same files as before the scoped-test step.

### Requirement: Missing scoped test path
When `plan_tests()` returns a test path that does not exist, stage MUST omit the path from `Reads:` and MUST record a warning in the plan.

#### Scenario: Scoped test path is missing
- **WHEN** `plan_tests()` returns a test path that does not exist in the repository.
- **THEN** The group's `Reads:` list does not contain that path, and the plan records a warning that names the path.
