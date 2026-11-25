## ADDED Requirements

### Requirement: Single-module narrowed run is serial
A narrowed `devops ci test` run with no `-n` and one target test module SHALL run pytest serially with `-n 0` and SHALL start no collection session.

#### Scenario: One fast module over 50 tests
- **WHEN** a test drives `devops ci test tests/roadmap/test_roadmap_claim.py` with `PYTEST_XDIST_AUTO_NUM_WORKERS` unset and records each pytest spawn
- **THEN** it sees one pytest spawn with `-n 0` and no spawn holding `--collect-only`

### Requirement: Multi-module narrowed run keeps the count rule
A narrowed `devops ci test` run with no `-n` and two or more target test modules SHALL keep the collected-test count rule.

#### Scenario: Two modules over the serial limit
- **WHEN** a test drives `devops ci test` for two target modules on a host with 16 CPUs and collection reports 51 tests
- **THEN** the test sees a `--collect-only` spawn and the test run uses `-n DEFAULT_CI_TEST_NARROWED_WORKERS`

### Requirement: Help text states the single-module rule
The `-n` help text of `devops ci test` SHALL state that a narrowed run to one target module runs serially with no collection session.

#### Scenario: The -n help line
- **WHEN** a test invokes `devops ci test --help` and reads the `-n` option text
- **THEN** the text states that a narrowed run to one target module runs serially with no collection session

## MODIFIED Requirements

### Requirement: Collection only when its count can change the workers
The command SHALL start no collection when the count cannot change the worker count. A narrowed run targeting one test module or a worker cap of 1 or less SHALL run pytest with `-n 0`. More than `DEFAULT_CI_TEST_SERIAL_MAX_TESTS` target modules with no `-k` filter SHALL run on the worker cap, because each module collects one test at least.

#### Scenario: Worker bound of a pod with 1 CPU
- **WHEN** `PYTEST_XDIST_AUTO_NUM_WORKERS` is 1 and the 7 selected files collect 399 tests.
- **THEN** The command runs pytest with `-n 0` and makes no collection call.

#### Scenario: More target modules than the test limit
- **WHEN** The caller passes `DEFAULT_CI_TEST_SERIAL_MAX_TESTS` + 1 test files and no `-k`.
- **THEN** The command runs pytest with `-n DEFAULT_CI_TEST_NARROWED_WORKERS` and makes no collection call.

#### Scenario: More target modules than the test limit with a filter
- **WHEN** The caller passes `DEFAULT_CI_TEST_SERIAL_MAX_TESTS` + 1 test files and `-k noop`.
- **THEN** The command makes one collection call.

### Requirement: Repeat runs take the workers of a narrowed run
A `--repeat` run of `devops ci test` SHALL use the given `-n`, or else the workers that a narrowed run of the same files and `-k` filter gets, chosen once for all of its runs. A run on workers SHALL give `--dist loadfile`, and a run on one process SHALL give no `--dist`. Above 50 tests across multiple target files, a run on workers does not catch a leak from one changed file into another changed file on another worker.

#### Scenario: Repeat run of many tests
- **WHEN** The caller passes `--repeat 2 --seed 5`, two test files that collect `DEFAULT_CI_TEST_SERIAL_MAX_TESTS` + 1 tests, and no `-n`.
- **THEN** The command makes one collection call, and runs pytest two times with `-n DEFAULT_CI_TEST_NARROWED_WORKERS` and `--dist loadfile`.

#### Scenario: Repeat run on one process
- **WHEN** The caller passes `--repeat 1 --seed 3 -n 0` and one test file.
- **THEN** The command runs pytest with no `--dist` option.

#### Scenario: Repeat run with given workers
- **WHEN** The caller passes `--repeat 2 --seed 1 -n 2` and one test file.
- **THEN** The command makes no collection call.
