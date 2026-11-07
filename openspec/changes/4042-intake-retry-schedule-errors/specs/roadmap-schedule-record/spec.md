## Purpose
What a roadmap round does with the `schedule.json` of a repository when the file exists and cannot be read: the round fails and names the file, and no row runs, so a damaged file never makes every row due at once.

## ADDED Requirements

### Requirement: An unreadable schedule stops the round
`run_due_jobs` SHALL raise `RoadmapRunError` that names the file and the remedy when `schedule.json` exists and is not valid JSON, is not a JSON object, holds a value that is not a string, or holds a value that is not an ISO timestamp. It MUST run no row and leave the file as it was.

#### Scenario: The file is not valid JSON
- **WHEN** A test writes `{not json` to `schedule.json` and runs a due round.
- **THEN** The round raises `RoadmapRunError` that names the file, and no row runs.

#### Scenario: The file is not an object
- **WHEN** A test writes a JSON list to `schedule.json` and runs a due round.
- **THEN** The round raises `RoadmapRunError` that names the file, and no row runs.

#### Scenario: A value is not a string
- **WHEN** A test writes `{"intake": 1760000000}` to `schedule.json` and runs a due round.
- **THEN** The round raises `RoadmapRunError` that names the file, and no row runs.

#### Scenario: A value is not a timestamp
- **WHEN** A test writes `{"intake": "yesterday"}` to `schedule.json` and runs a due round.
- **THEN** The round raises `RoadmapRunError` that names the file, and no row runs.

### Requirement: A missing schedule is a first run
A repository with no `schedule.json` SHALL read as having no last success, and the rows with a first run SHALL be due.

#### Scenario: The file does not exist
- **WHEN** A test runs a due round for a repository with no `schedule.json`.
- **THEN** The round runs the rows that are due on a first run and raises no error.
