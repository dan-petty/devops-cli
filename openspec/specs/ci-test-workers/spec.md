# ci-test-workers Specification

## Purpose
How `devops ci test` chooses the number of pytest workers for a run that given paths narrow, so that a selection of many slow tests runs in parallel and a tiny selection stays serial.

## Requirements

### Requirement: Collected tests choose the workers
`devops ci test` SHALL choose the worker count of a run given no `-n` from the number of tests that the selection collects, not from the number of files. It SHALL start no more workers than the worker cap: `DEFAULT_CI_TEST_NARROWED_WORKERS`, or the value of `PYTEST_XDIST_AUTO_NUM_WORKERS` when that value is a smaller whole number. It SHALL ignore a value that is no whole number, as xdist does.

#### Scenario: Many tests in few files
- **WHEN** The selected files collect more than `DEFAULT_CI_TEST_SERIAL_MAX_TESTS` tests and the caller gives no `-n`.
- **THEN** The command runs pytest with `-n DEFAULT_CI_TEST_NARROWED_WORKERS`.

#### Scenario: Worker bound of a pod with 2 CPUs
- **WHEN** `PYTEST_XDIST_AUTO_NUM_WORKERS` is 2 and the 7 selected files collect 399 tests.
- **THEN** The command runs pytest with `-n 2`.

#### Scenario: Selected module with unused snapshots
- **WHEN** The 7 selected files collect 422 tests, and the collection exits 1 without `--snapshot-warn-unused` and 0 with it, as syrupy does for a selected module that has snapshots.
- **THEN** The command runs pytest with `-n DEFAULT_CI_TEST_NARROWED_WORKERS` and prints no collection warning.

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
The command MUST collect tests with the same target list and keyword filter that it passes to pytest, and with `--snapshot-warn-unused`, so that the snapshots that a collection leaves unused do not fail it.

#### Scenario: Collection command arguments
- **WHEN** The caller passes two test files and `-k slow`.
- **THEN** The collection command holds both file paths, `-k slow` and `--snapshot-warn-unused`.

### Requirement: Collection failure falls back
When pytest collection fails or runs past `DEFAULT_CI_TEST_COLLECTION_TIMEOUT_SECONDS`, the command SHALL fall back to the file-count rule and continue: up to `DEFAULT_CI_TEST_SERIAL_MAX_FILES` test modules run with `-n 0`, and more modules run on the worker cap. The warning SHALL show the collection command as text, not as Rich markup. An exit code 5, which says that no test was collected, is a count of zero and no failure.

#### Scenario: Collection error at the file bound
- **WHEN** The collection command exits with code 3 for a selection of 12 test files.
- **THEN** The command runs pytest with `-n 0` and prints a warning that names the collection failure.

#### Scenario: Collection error above the file bound
- **WHEN** The collection command exits with code 3 for a selection of 13 test files.
- **THEN** The command runs pytest with `-n DEFAULT_CI_TEST_NARROWED_WORKERS` from the file-count rule and prints a warning that names the collection failure.

#### Scenario: Collection timeout
- **WHEN** The collection command runs past its timeout for a selection of 13 test files.
- **THEN** The command runs pytest with `-n DEFAULT_CI_TEST_NARROWED_WORKERS` and prints a warning that names a timeout of `DEFAULT_CI_TEST_COLLECTION_TIMEOUT_SECONDS`.

#### Scenario: Brackets in the keyword filter
- **WHEN** The collection command exits with code 3 and the caller passes `-k noop[/x]`.
- **THEN** The command exits 0 and the warning shows `noop[/x]` as it is.

#### Scenario: No test matches the filter
- **WHEN** The collection command exits with code 5 for the selection.
- **THEN** The command runs pytest with `-n 0` and prints no collection warning.

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

### Requirement: Collection only when its count can change the workers
The command SHALL start no collection when the count cannot change the worker count. A worker cap of 1 or less SHALL run pytest with `-n 0`. More than `DEFAULT_CI_TEST_SERIAL_MAX_TESTS` target modules with no `-k` filter SHALL run on the worker cap, because each module collects one test at least.

#### Scenario: Worker bound of a pod with 1 CPU
- **WHEN** `PYTEST_XDIST_AUTO_NUM_WORKERS` is 1 and the 7 selected files collect 399 tests.
- **THEN** The command runs pytest with `-n 0` and makes no collection call.

#### Scenario: More target modules than the test limit
- **WHEN** The caller passes `DEFAULT_CI_TEST_SERIAL_MAX_TESTS` + 1 test files and no `-k`.
- **THEN** The command runs pytest with `-n DEFAULT_CI_TEST_NARROWED_WORKERS` and makes no collection call.

#### Scenario: More target modules than the test limit with a filter
- **WHEN** The caller passes `DEFAULT_CI_TEST_SERIAL_MAX_TESTS` + 1 test files and `-k noop`.
- **THEN** The command makes one collection call.

### Requirement: Repeat runs make no collection
A `--repeat` run SHALL run each repeat with `-n 0` and make no collection call.

#### Scenario: Repeat run
- **WHEN** The caller passes `--repeat 2 --seed 1` and one test file.
- **THEN** The command makes no collection call.
