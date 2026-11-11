## ADDED Requirements

### Requirement: The verify command creates its own report file
`devops roadmap eval verify` SHALL create a report file with a name unique to the run in the verify store folder when `--resume` is absent, and SHALL write every later report of that run to the file that it created.

#### Scenario: Two runs start in one second
- **WHEN** Two runs start with no `--resume` while the clock reads one second, and both write their reports.
- **THEN** The verify store folder holds two `.json` reports, and each report holds only the cases of its run.

#### Scenario: A case ends and the report is written
- **WHEN** A run without `--resume` ends a case and writes the report.
- **THEN** The write goes to the report file that the run got at its start.

### Requirement: A resumed run keeps the report it names
`devops roadmap eval verify --resume <report>` SHALL write only the report that `--resume` names, and SHALL create no new report file for that run.

#### Scenario: A run resumes a report
- **WHEN** A run starts with `--resume` of a report that exists.
- **THEN** The run writes that file, and the verify store folder holds no new report file.

### Requirement: A store file gets a unique name
The store file helper SHALL create the store folder when it is absent, SHALL create the file exclusively, and SHALL give each call in one second a different name.

#### Scenario: The helper runs two times in one second
- **WHEN** The helper is called two times while the clock reads one second, and the store folder is absent.
- **THEN** The helper creates the folder, returns two different paths, and both files exist.
