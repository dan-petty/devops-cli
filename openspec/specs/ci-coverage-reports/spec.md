# ci-coverage-reports Specification

## Purpose
Which coverage reports and data files the `devops ci` test row writes and keeps, and where CI's changed-line coverage step gets the XML report that diff-cover reads.

## Requirements

### Requirement: The test row writes no XML report
The `devops ci` test row SHALL run pytest with `--cov=src` and the `term-missing` report, and SHALL NOT ask pytest-cov for an XML report.

#### Scenario: The test row's command
- **WHEN** the gate builds the command of its test row
- **THEN** the command holds `--cov=src` and `--cov-report=term-missing`, and no `--cov-report=xml` argument

### Requirement: The coverage clean-up keeps the combined data
The coverage clean-up of `devops ci` SHALL remove only the `.coverage.*` worker data files of the checked tree and of `.data/`, and SHALL keep the combined data file `.data/.coverage`, whatever its age.

#### Scenario: A combined data file two hours old and two worker files
- **WHEN** the clean-up runs with `force` on a tree that holds `.data/.coverage`, two hours old, and the worker files `.data/.coverage.host.pid4242.Xabcdef` and `.coverage.host.pid4243.Xabcdeg`
- **THEN** `.data/.coverage` still exists and both worker files are gone

### Requirement: CI writes the XML report where diff-cover reads it
The `Changed-Line Coverage` step of the `test` job in `.github/workflows/ci.yml` SHALL run `uv run coverage xml` from the data that the job combined from the shards with `coverage combine`, before diff-cover reads `.data/coverage.xml`.

#### Scenario: The order of the step's commands
- **WHEN** the `Changed-Line Coverage` step of `ci.yml` is read
- **THEN** its script runs `uv run coverage xml` before `diff-cover .data/coverage.xml`

#### Scenario: The combined data comes first
- **WHEN** the steps of the `test` job are read
- **THEN** the step that runs `coverage combine` comes before the step `Changed-Line Coverage`

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
