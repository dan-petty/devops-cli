## Purpose

Which coverage reports and data files the `devops ci` test row writes and keeps, and where CI's changed-line coverage step gets the XML report that diff-cover reads.

## ADDED Requirements

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
The `Changed-Line Coverage` step of the `test` job in `.github/workflows/ci.yml` SHALL run `uv run coverage xml` from the combined data that the gate keeps, before diff-cover reads `.data/coverage.xml`.

#### Scenario: The order of the step's commands
- **WHEN** the `Changed-Line Coverage` step of `ci.yml` is read
- **THEN** its script runs `uv run coverage xml` before `diff-cover .data/coverage.xml`
