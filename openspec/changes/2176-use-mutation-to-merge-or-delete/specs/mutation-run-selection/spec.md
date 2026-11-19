## Purpose
How the mutation run selects the tests it runs inside its copy of the tree, so that a stats run completes on this tree and names only test paths that a file of this tree holds.

## ADDED Requirements

### Requirement: The mutation selection names test paths of this tree
The mutation run MUST select only test paths that a file of this tree holds, and MUST leave out only tests that those files define.

#### Scenario: Each left-out test is a test of this tree
- **WHEN** `uv run pytest --collect-only -q <node id>` runs for the node id of each `--deselect` entry of `pytest_add_cli_args_test_selection`, and `test -f` runs for the path of each `--ignore` entry
- **THEN** pytest collects one test for each node id, and each path is a file

#### Scenario: The selection passes in the mutants tree
- **WHEN** pytest runs the selection of `pyproject.toml` in the mutants tree that mutmut makes for all of `src/devops_cli`
- **THEN** each selected test passes, so the stats run of `uv run devops ci mutate <path>` does not stop at a failed test

### Requirement: The mutation run copies the files that its tests read
The mutation run MUST copy into its tree each top-level entry of the checkout that a selected test reads, the living specs included.

#### Scenario: A test that reads a living spec
- **WHEN** `tests/openspec/test_openspec_new.py` runs in the mutants tree
- **THEN** it finds the spec of `openspec/specs` that it reads, and passes
