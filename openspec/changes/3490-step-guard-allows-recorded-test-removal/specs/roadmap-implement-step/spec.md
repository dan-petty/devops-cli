## MODIFIED Requirements

### Requirement: A step keeps the tests that existed
Every test that a `.py` file under `tests/` held at the commit where the step started SHALL be in the checkout after the run, by qualified name (`test_x` or `Class.test_x`), unless the caller of the step gives its `path::name` in `recorded_tests`. A test is a function named `test_*`. When any other test is lost, the step SHALL stop with a reason that names the file and at most `CONST_ROADMAP_IMPLEMENT_REASON_TESTS` of its tests, and SHALL give no extra turn. A file that does not parse is skipped.

#### Scenario: A test file that the agent replaces
- **WHEN** a test file holds `test_a` and `test_b` at the start, and the model writes a file that holds `test_c`
- **THEN** the step reports stopped, the reason names the file, `test_a` and `test_b`, and the checkout is reset

#### Scenario: A test that the agent adds
- **WHEN** the model adds `test_c` to a test file that holds `test_a` and `test_b`
- **THEN** the step reports done

#### Scenario: A test that the agent renames
- **WHEN** the model renames `test_a` to `test_z` in its file
- **THEN** the step reports stopped, and the reason names `test_a`

#### Scenario: A test file that the agent deletes
- **WHEN** the model deletes a test file that holds `test_a`
- **THEN** the step reports stopped, and the reason names the file and `test_a`

#### Scenario: A test that the agent moves
- **WHEN** the model moves `Check.test_a` from one test file to a new test file
- **THEN** the step reports stopped, and the reason names the old file and `Check.test_a`

#### Scenario: A test that loses its body
- **WHEN** the model keeps the name of `test_a` and replaces its body with `pass`
- **THEN** this check does not stop the step: it reads names only

#### Scenario: A file that does not parse
- **WHEN** a test file has a syntax error after the run, or at the start
- **THEN** this check does not stop the step, and the static check judges the file

#### Scenario: A long list of lost tests
- **WHEN** the model drops more than `CONST_ROADMAP_IMPLEMENT_REASON_TESTS` tests of a file
- **THEN** the reason names that many tests in order and gives the count of the rest

#### Scenario: A removal that the record names
- **WHEN** the model removes `test_a`, and `recorded_tests` holds `tests/test_old.py::test_a`
- **THEN** the step reports done

#### Scenario: A rename or a move that the record names
- **WHEN** the model renames `test_a` to `test_z` or moves it to a new test file, and `recorded_tests` holds the old `path::name`
- **THEN** the step reports done

#### Scenario: A removal that the record does not name
- **WHEN** the model removes `test_a` and `test_b`, and `recorded_tests` holds only `tests/test_old.py::test_a`
- **THEN** the step reports stopped with the class `tests_lost`, and the reason names `test_b` and not `test_a`

#### Scenario: A kept task with a recorded removal
- **WHEN** the agent ticks a task whose verification passes, and the only test that it lost is in `recorded_tests`
- **THEN** the keeper makes the `wip:` commit

#### Scenario: The prompt of the step
- **WHEN** a test reads `roadmap_implement_step.md`
- **THEN** the rule of the tests names the `## Weakened checks` section, and says that an entry from the agent does not count
