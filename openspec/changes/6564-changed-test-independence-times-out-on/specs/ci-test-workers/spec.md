## REMOVED Requirements

### Requirement: Repeat runs make no collection
**Reason**: A serial run of a large set of changed tests takes more time than the job limit of CI. One run of 1,473 tests took 454 s on one process (#6564).
**Migration**: The requirement `Repeat runs take the workers of a narrowed run` replaces it.

## ADDED Requirements

### Requirement: Repeat runs take the workers of a narrowed run
A `--repeat` run of `devops ci test` SHALL use the given `-n`, or else SHALL choose its workers as a narrowed run of the same files and `-k` filter does. It SHALL choose the workers once, and SHALL start each of its runs on those workers.

#### Scenario: Repeat run of many tests
- **WHEN** The caller passes `--repeat 2 --seed 5`, one test file that collects `DEFAULT_CI_TEST_SERIAL_MAX_TESTS` + 1 tests, and no `-n`.
- **THEN** The command makes one collection call, and runs pytest two times with `-n DEFAULT_CI_TEST_NARROWED_WORKERS`.

#### Scenario: Repeat run with given workers
- **WHEN** The caller passes `--repeat 2 --seed 1 -n 2` and one test file.
- **THEN** The command makes no collection call.
