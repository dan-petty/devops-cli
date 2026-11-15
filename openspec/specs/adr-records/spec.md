# adr-records Specification

## Purpose
The citation rule of the ADR process: code, tests and workflows name the record in force, and a test fails on a citation of a superseded record outside the history.

## Requirements

### Requirement: Code, tests and workflows cite the record in force
A test SHALL read the status from the front matter of each `docs/adr/*.md` and SHALL fail on an `ADR <number>` citation in `src/`, `tests/` or `.github/` whose record is superseded. Archived change folders, `CHANGELOG.md` and `docs/adr/` SHALL stay out of the scan.

#### Scenario: A citation of a superseded record
- **WHEN** a source file cites `ADR 0003`, which is superseded
- **THEN** the test fails and names the file and the line

#### Scenario: The history
- **WHEN** a file under `openspec/changes/archive/`, `CHANGELOG.md` or `docs/adr/` cites a superseded record
- **THEN** the test passes

#### Scenario: A citation of a record in force
- **WHEN** a file cites `ADR 0021`
- **THEN** the test passes
