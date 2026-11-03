## ADDED Requirements

### Requirement: The plan lists the registry and ratchet places that its changes need
The stage job SHALL build the registry and ratchet table from the module-level `REGISTRY_COUNTS` declarations of the test modules, and MUST NOT read a hand-copied table. The plan context SHALL list each matching entry with its `path:line`, and `check_proposal` MUST refuse a plan that adds a counted item and has no task whose text names the declared path.

#### Scenario: A new declaration appears in the table
- **WHEN** A test module adds a `REGISTRY_COUNTS` entry for a counted prefix, enum or table name.
- **THEN** The table builder returns that entry with its test path and line, and no hand-written table changes.

#### Scenario: New roadmap limit without a ratchet task
- **WHEN** A plan adds `DEFAULT_ROADMAP_EXAMPLE_LIMIT` and has no task for `tests/roadmap/test_roadmap_limit_classes.py`.
- **THEN** The context names `tests/roadmap/test_roadmap_limit_classes.py` and `check_proposal` returns a missing-path problem for it.

#### Scenario: New job write without one registry task
- **WHEN** A plan adds a write method and has no task for `tests/roadmap_faults.py`.
- **THEN** The context names `tests/roadmap/test_roadmap_dry_runs.py`, the `WRITES` table in `tests/roadmap_faults.py`, `tests/roadmap/test_roadmap_store_contract.py` and `src/devops_cli/roadmap/request_plan.py`, and `check_proposal` returns a problem for the fault-test path.

#### Scenario: A plan that names every listed place passes
- **WHEN** A plan adds a counted item and holds a task whose text names each declared path.
- **THEN** `check_proposal` returns no registry problem for that plan.

### Requirement: A test path in a docstring or a spec names a file of the commit
`check_proposal` SHALL fail when a test file path named in a Python docstring or in a spec names no file of the commit, and MUST add each such path to its refusal list.

#### Scenario: A spec names a missing test file
- **WHEN** A spec contains `tests/test_missing_example.py` and that file is absent from the commit.
- **THEN** The check reports `tests/test_missing_example.py` as a missing path.

#### Scenario: A plan changes a docstring with a stale test path
- **WHEN** A plan changes a Python file whose docstring names a test file that the commit does not hold.
- **THEN** `check_proposal` returns a problem that names the missing test path.

#### Scenario: A docstring that names a test file of the commit passes
- **WHEN** A Python file names `tests/roadmap/test_roadmap_limit_classes.py` in its docstring and the commit holds that file.
- **THEN** The check reports no missing path.
