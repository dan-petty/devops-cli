## ADDED Requirements

### Requirement: The mutation run takes its test selection from the mutmut table
While `mutmut run` runs, the mutation run of the strength check SHALL give the scoped test modules to mutmut in `pytest_add_cli_args_test_selection` of `[tool.mutmut]` in the `pyproject.toml` of the checkout, after the entries of that table. The command SHALL set no environment key that `build_subprocess_env` refuses.

#### Scenario: Two scoped test modules
- **WHEN** the table holds `--ignore=tests/test_docs.py` and the mutation run gets `tests/test_sample.py` and `tests/test_other.py`
- **THEN** while `mutmut run` runs, the selection is `--ignore=tests/test_docs.py`, `tests/test_sample.py` and `tests/test_other.py`

#### Scenario: The environment of the run
- **WHEN** the environment that the mutation run gives to `run_subprocess` goes to `build_subprocess_env`
- **THEN** no `SecurityError` occurs, and the child environment holds no `PYTEST_ADDOPTS`

### Requirement: The mutation run leaves the mutmut table as it found it
After the mutation run, the `pyproject.toml` of the checkout SHALL hold the bytes that it held before the run, also when the command raises or reaches the timeout. A checkout with no `pyproject.toml` SHALL have none after the run. With no scoped test module, the run SHALL leave the file as it is.

#### Scenario: A finished run
- **WHEN** the mutation run with two scoped test modules ends
- **THEN** the file holds its original text

#### Scenario: A run that reaches the timeout in a checkout with no pyproject.toml
- **WHEN** the checkout has no `pyproject.toml` and `mutmut run` reaches the timeout
- **THEN** the selection during the run is the scoped test module, and the checkout has no `pyproject.toml` after the run
