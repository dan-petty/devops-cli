## ADDED Requirements

### Requirement: The mutation run mutates only the files of its targets and removes its tree
While `mutmut run` and `mutmut results` run, the mutation run of the strength check SHALL set `only_mutate` of `[tool.mutmut]` in the `pyproject.toml` of the checkout to the files of its targets, each file once. After it reads the results, it SHALL remove the directory `mutants/` of the checkout, also when a command raises or reaches the timeout.

#### Scenario: Three targets in two files
- **WHEN** the mutation run gets two targets in `src/sample.py` and one target in `src/other.py`
- **THEN** `only_mutate` is `src/sample.py` and `src/other.py` while `mutmut run` and `mutmut results` run, and the checkout has no `mutants/` after the run

#### Scenario: A run that reaches the timeout
- **WHEN** `mutmut run` reaches the timeout after it wrote `mutants/`
- **THEN** the run reads the results, and the checkout has no `mutants/` after the run
