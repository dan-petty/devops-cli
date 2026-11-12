## Purpose
How `devops ci test` chooses the number of pytest workers for a run that given paths narrow, so that a selection of many slow tests runs in parallel and a tiny selection stays serial.

## ADDED Requirements

### Requirement: Collected tests choose the workers
`devops ci test` SHALL choose the worker count of a run given no `-n` from the number of tests that the selection collects, not from the number of files.

#### Scenario: Many tests in few files
- **WHEN** The selected files collect more than `DEFAULT_CI_TEST_SERIAL_MAX_TESTS` tests and the caller gives no `-n`.
- **THEN** The command runs pytest with `-n DEFAULT_CI_TEST_NARROWED_WORKERS`.

### Requirement: Small selections stay serial
`devops ci test` SHALL run pytest with `-n 0` when the selection collects no more than `DEFAULT_CI_TEST_SERIAL_MAX_TESTS` tests.

#### Scenario: Few collected tests
- **WHEN** The selected files collect 12 tests and the caller gives no `-n`.
- **THEN** The command runs pytest with `-n 0`.

### Requirement: Keyword filter changes the count
The worker decision SHALL count only the tests that match the `-k` filter.

#### Scenario: Keyword filter leaves few tests
- **WHEN** The selected files collect 399 tests and `-k` matches 5 tests.
- **THEN** The command runs pytest with `-n 0`.

### Requirement: Collection uses the run selection
The command MUST collect tests with the same target list and keyword filter that it passes to pytest.

#### Scenario: Collection command arguments
- **WHEN** The caller passes two test files and `-k slow`.
- **THEN** The collection command holds both file paths and `-k slow`.

### Requirement: Collection failure falls back
When pytest collection fails or times out, the command SHALL fall back to the file-count rule and continue.

#### Scenario: Collection error
- **WHEN** The collection command exits non-zero for a selection of 7 files.
- **THEN** The command uses the file-count rule and prints a warning that names the collection failure.

### Requirement: Explicit workers win
An explicit `-n` value from the caller MUST override the automatic worker count.

#### Scenario: Explicit worker count
- **WHEN** The caller passes `-n 2` for a selection of 399 tests.
- **THEN** The command runs pytest with `-n 2` and makes no collection call.

### Requirement: Full suite keeps addopts
A run with no paths SHALL pass no `-n` value, so `addopts` applies.

#### Scenario: Full suite run
- **WHEN** The caller passes no paths.
- **THEN** The command runs pytest with no `-n` option and makes no collection call.
