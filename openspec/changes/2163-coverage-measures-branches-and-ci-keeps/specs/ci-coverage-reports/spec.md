## ADDED Requirements

### Requirement: branch-coverage-measurement
The coverage configuration SHALL set `branch = true` in `[tool.coverage.run]` so that coverage.py measures both sides of each conditional.

#### Scenario: branch key present in pyproject
- **WHEN** pyproject.toml is parsed and the [tool.coverage.run] table is read
- **THEN** the table contains the key `branch` with the value `true`

### Requirement: coverage-xml-artifact-upload
The `Tests & Coverage` job SHALL upload `.data/coverage.xml` as a CI artifact with a retention period of at most 14 days.

#### Scenario: upload step in workflow
- **WHEN** the `Tests & Coverage` job in .github/workflows/ci.yml is read
- **THEN** it contains a step that uses `actions/upload-artifact` with `path` set to `.data/coverage.xml` and a `retention-days` input
