## MODIFIED Requirements

### Requirement: CI writes the XML report where diff-cover reads it
The `Changed-Line Coverage` step of the `test` job in `.github/workflows/ci.yml` SHALL run `uv run coverage xml` from the data that the job combined from the shards with `coverage combine`, before diff-cover reads `.data/coverage.xml`.

#### Scenario: The order of the step's commands
- **WHEN** the `Changed-Line Coverage` step of `ci.yml` is read
- **THEN** its script runs `uv run coverage xml` before `diff-cover .data/coverage.xml`

#### Scenario: The combined data comes first
- **WHEN** the steps of the `test` job are read
- **THEN** the step that runs `coverage combine` comes before the step `Changed-Line Coverage`
