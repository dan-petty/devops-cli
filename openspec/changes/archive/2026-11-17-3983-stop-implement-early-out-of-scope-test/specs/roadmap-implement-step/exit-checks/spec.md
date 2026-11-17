## ADDED Requirements

### Requirement: Stop on out-of-scope invariant test
The implement runner SHALL stop the step when an invariant test fails on a file outside the `Changes:` list.

#### Scenario: Invariant test outside `Changes:` stops the step
- **WHEN** the step exit check reports a failing invariant test whose file is not in the group's `Changes:` list and is not the change's `tasks.md`
- **THEN** the step ends with a stop result and starts no fix step

### Requirement: Stop names the test and path
The stop SHALL name the failing test and the path outside `Changes:`.

#### Scenario: Stop evidence names the failing test and its path
- **WHEN** the guard stops a step for an out-of-scope test failure
- **THEN** the stop result holds the test identifier and its file path, and the item comment shows both

### Requirement: Stop spends no further tokens
The stop SHALL not spend the remaining token budget on edit attempts.

#### Scenario: No model request follows the stop
- **WHEN** the guard stops a step for an out-of-scope test failure
- **THEN** the step makes no model request after the stop and the recorded token spend does not increase

### Requirement: Offline test covers the guard
An offline test SHALL cover a failing invariant test outside `Changes:`.

#### Scenario: Offline test feeds a failing invariant test outside `Changes:`
- **WHEN** the offline test supplies a step result with a failing invariant test whose file is outside `Changes:`
- **THEN** the runner returns the stop with the test and path and makes no fix attempt
