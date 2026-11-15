## ADDED Requirements

### Requirement: A workflow change carries its contract test in the same group
`path_problems` SHALL report a problem for each file under `.github/workflows/` with the suffix `.yml` that a group lists in `changes` when the `changes` of that group holds no `tests/invariants/test_workflow_contracts.py`. The problem SHALL name the group, the workflow and the contract test. The rule SHALL read `changes` only, so a group that reads a workflow and changes no workflow needs no contract test.

#### Scenario: A workflow change without the contract test
- **WHEN** a group lists `.github/workflows/ci.yml` in `changes` and holds no `tests/invariants/test_workflow_contracts.py`
- **THEN** `path_problems` returns one problem, and it names the group, the workflow and the contract test

#### Scenario: A workflow change with the contract test
- **WHEN** a group lists `.github/workflows/ci.yml` and `tests/invariants/test_workflow_contracts.py` in `changes`
- **THEN** `path_problems` returns no problem for the workflow contract rule

#### Scenario: A source change that reads a workflow
- **WHEN** a group reads `.github/workflows/ci.yml` and changes only a file under `src/`
- **THEN** `path_problems` returns no problem for the workflow contract rule

#### Scenario: Each workflow file of a group
- **WHEN** a group lists `.github/workflows/ci.yml` and `.github/workflows/release.yml` in `changes` and holds no contract test
- **THEN** `path_problems` returns one problem for each workflow file
