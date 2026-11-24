# ci-gate-rows Specification Delta

## ADDED Requirements

### Requirement: The table holds a hadolint row that runs the pre-commit hook
The table of `devops ci` SHALL hold a row `hadolint` whose command runs `uv run pre-commit run hadolint --all-files`.

#### Scenario: The row is the hadolint pre-commit hook
- **WHEN** `devops ci --only hadolint --dry-run` runs
- **THEN** the plan shows `uv run pre-commit run hadolint --all-files`
