# ci-test-selection Specification

## Purpose
How `devops ci test` turns its path arguments into the test modules that pytest runs, and when it refuses a path instead of reporting success without a test.

## ADDED Requirements

### Requirement: A directory argument selects tests or is refused
`devops ci test` SHALL expand a directory under `tests/` to the test modules inside it, at any depth. It SHALL expand a directory under `src/` to the Python modules inside it and map them to tests as it maps a file. It SHALL refuse a directory that gives no module, and a directory outside `src/` and `tests/`, with exit status 1 and an error that names the directory, and SHALL start no pytest.

#### Scenario: A tests directory runs its test modules
- **WHEN** `devops ci test tests/pkg` runs, and `tests/pkg` holds `test_a.py`, `deep/test_b.py` and `helper.py`
- **THEN** pytest is started with `tests/pkg/test_a.py` and `tests/pkg/deep/test_b.py`
- **AND** `tests/pkg/helper.py` is not among its arguments

#### Scenario: A tests directory without a test module is refused
- **WHEN** `devops ci test tests/empty` runs, and `tests/empty` holds no test module
- **THEN** the command exits with status 1 and its error names `tests/empty`
- **AND** no pytest is started

#### Scenario: A directory outside the source and test trees is refused
- **WHEN** `devops ci test docs` runs
- **THEN** the command exits with status 1 and its error names `docs`
- **AND** no pytest is started

#### Scenario: A source directory runs the tests that cover its modules
- **WHEN** `devops ci test src/devops_cli/security` runs, and a test module imports a module of that directory
- **THEN** pytest is started with that test module

#### Scenario: A file that maps to no test still passes
- **WHEN** `devops ci test README.md` runs
- **THEN** the command exits with status 0 and starts no pytest

### Requirement: A path that does not exist is refused
`devops ci test` SHALL refuse a path that does not exist, with exit status 1 and an error that names the path, and SHALL start no pytest. A trigger file that is gone, such as a deleted `conftest.py`, SHALL still force the full run.

#### Scenario: A path that does not exist is refused
- **WHEN** `devops ci test tests/missing` runs, and `tests/missing` does not exist, with or without `--fallback`
- **THEN** the command exits with status 1 and its error names `tests/missing`
- **AND** no pytest is started

#### Scenario: A deleted trigger file still forces the full run
- **WHEN** `devops ci test conftest.py` runs, and `conftest.py` does not exist
- **THEN** the command runs the full suite
