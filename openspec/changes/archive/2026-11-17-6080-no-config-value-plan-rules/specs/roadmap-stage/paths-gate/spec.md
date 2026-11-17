## REMOVED Requirements

### Requirement: A workflow change carries its contract test in the same group
**Reason**: The rule made each plan of a workflow change `tests/invariants/test_workflow_contracts.py`, a test that asserts values of a config file (#6080). Actionlint and zizmor check a workflow through `devops ci`.
**Migration**: The requirement "A workflow change needs no test" holds the rule.

### Requirement: The stage prompt asks for the contract test of a workflow change
**Reason**: The rule of the workflow contract test is removed (#6080), and the stage prompt holds no such instruction.
**Migration**: None. The stage prompt names `uv run devops ci --check --only actionlint,zizmor` as the proof of a workflow.

## ADDED Requirements

### Requirement: A workflow change needs no test
`path_problems` SHALL report no problem for a group that changes a workflow under `.github/workflows/` and lists no test in `changes`, because actionlint and zizmor check the workflow through `devops ci`.

#### Scenario: A workflow change with the actionlint and zizmor check
- **WHEN** a group changes `.github/workflows/sample.yml`, lists no test in `changes` and gives the `verify` command `uv run devops ci --check --only actionlint,zizmor`
- **THEN** `path_problems` returns no problem
