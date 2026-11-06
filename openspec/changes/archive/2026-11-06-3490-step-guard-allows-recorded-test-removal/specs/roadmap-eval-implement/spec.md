## MODIFIED Requirements

### Requirement: The property tests_kept finds a lost or weakened test
`tests_kept` SHALL fail when the diff deletes a Python file under `tests/`, removes a test name that no added line of the same file defines, takes assertion lines from a test on balance, or adds a skip or xfail to a test whose `def` stays, unless `allow_lost_tests` of the fixture allows that `path::name`. `load_case` SHALL add each `path::name` that the `## Weakened checks` section of the plan names to that list, and `run_case` SHALL give the same list to the step.

#### Scenario: A deleted test
- **WHEN** the diff deletes `tests/test_sample.py`, which defined `test_a`
- **THEN** `tests_kept` fails and names `tests/test_sample.py::test_a`

#### Scenario: A test that moves in its file
- **WHEN** the diff removes `def test_a` from one place of a test file and adds it at another place of the same file
- **THEN** `tests_kept` passes

#### Scenario: A deletion item that allows a lost test
- **WHEN** the diff removes `test_dead` and the fixture allows `tests/test_sample.py::test_dead`
- **THEN** `tests_kept` passes

#### Scenario: A test that becomes a stub
- **WHEN** the diff replaces the assertion lines of `test_y` with `pass`, or removes `test_y` and adds a `test_y` with no assertion
- **THEN** `tests_kept` fails and names `tests/test_sample.py::test_y` as weakened

#### Scenario: A skip on an existing test
- **WHEN** the diff adds `@pytest.mark.skip` above a `test_y` that already exists
- **THEN** `tests_kept` fails and names `tests/test_sample.py::test_y` as weakened

#### Scenario: A removal that the plan of the fixture records
- **WHEN** the diff removes `test_a`, and the `proposal.md` of the fixture names `tests/test_sample.py::test_a` in an entry of `## Weakened checks`
- **THEN** `allow_lost_tests` holds `tests/test_sample.py::test_a`, and `tests_kept` passes

#### Scenario: A removal that the plan of the fixture does not record
- **WHEN** the diff removes `test_b`, and the section names only `tests/test_sample.py::test_a`
- **THEN** `tests_kept` fails and names `tests/test_sample.py::test_b`

#### Scenario: A test of a class that the plan of the fixture records
- **WHEN** the diff removes `def test_a` from `class TestKept`, and the section names `tests/test_sample.py::TestKept.test_a`
- **THEN** `tests_kept` passes, and the step guard allows the same removal through the same entry

#### Scenario: The step of a fixture reads the list
- **WHEN** `run_case` runs a fixture whose list holds a test, and the scripted model removes that test
- **THEN** the step reports done
