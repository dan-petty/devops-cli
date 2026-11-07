## ADDED Requirements

### Requirement: The aggregate job keeps the coverage XML as an artifact
The job `test`, named `Tests & Coverage`, in `.github/workflows/ci.yml` SHALL upload `.data/coverage.xml` with `actions/upload-artifact` in a step after `Changed-Line Coverage`, pinned by a full commit SHA, with `retention-days: 7` and `include-hidden-files: true`.

#### Scenario: The job uploads the report
- **WHEN** a test reads the steps of the job `test` in `.github/workflows/ci.yml`
- **THEN** one step after `Changed-Line Coverage` uses `actions/upload-artifact` pinned by a 40-character commit SHA with `path: .data/coverage.xml`, `include-hidden-files: true` and `retention-days: 7`

#### Scenario: The report survives a failed changed-line gate
- **WHEN** the `Changed-Line Coverage` step exits non-zero
- **THEN** the upload step carries `if: always()` and `if-no-files-found: warn`, so it runs and a missing report warns instead of failing

#### Scenario: A run that writes no report warns
- **WHEN** a push to main or a plan-only pull request runs the job
- **THEN** the upload step writes no artifact and adds no failure, because `if-no-files-found: warn` holds it to a warning
