## ADDED Requirements

### Requirement: The verify command stores each case when it ends
`devops roadmap eval verify` SHALL write its report to the file under `.data/roadmap_eval/verify/` at the start of the run and again when each case ends, and SHALL name the file when the run starts. A stop of the run SHALL leave the cases that ended in the file.

#### Scenario: A stop in the third case
- **WHEN** the run of three cases stops in the third case
- **THEN** the store got the score of no case, then of the first case, then of the first two cases

### Requirement: Each write leaves a complete report
Each write of the report SHALL replace the whole file atomically, so the file is always a complete report that lists the cases that ended, with their findings.

#### Scenario: The file after the first case
- **WHEN** a test reads the report file while the second case runs
- **THEN** the file parses as JSON and lists the first case with its findings

### Requirement: Rejected credentials keep the cases that ended
Rejected credentials SHALL stop the run with an error and SHALL keep in the report file the cases that ended before the rejection.

#### Scenario: Credentials refused in the second case
- **WHEN** the model fake raises `AICredentialsError` in the second case of three
- **THEN** the command exits with an error, the model fake records two calls, and the report file lists the first case only

### Requirement: The verify command resumes a stored report
`devops roadmap eval verify --resume <report>` SHALL run only the cases that the report lacks or that failed in it. It SHALL keep the other cases of the report unchanged, merge them with the new outcomes into one score, and write that score to the same file. The cases of the run SHALL be the cases that `--case` and `--limit` select and the cases that the report holds. `--dry-run` with `--resume` SHALL list only the cases that would run.

#### Scenario: A resume of a report with a failed case and a missing case
- **WHEN** the report holds two cases that ended and one failed case, the set holds one more case, and the command runs with `--resume` of that report
- **THEN** the model fake records calls for the failed case and the missing case only, the report file lists all four cases with the two first cases unchanged, and no new report file is written

#### Scenario: A resume with a smaller selection
- **WHEN** the report holds one case and the command runs with `--case` for a second case and `--resume` of that report
- **THEN** the model fake records a call for the second case only, and the report file lists both cases

#### Scenario: The dry run of a resume
- **WHEN** the report holds one of two cases and the command runs with `--resume` and `--dry-run`
- **THEN** the output lists the other case only, and the model fake records no call

### Requirement: A resume refuses a report that it cannot merge
A report of another model, a report that holds a case that the set lacks, or a file that is not a report SHALL stop `devops roadmap eval verify --resume` with exit status 1 before any model call.

#### Scenario: A report of another model
- **WHEN** the report is of the model `m-1` and the command runs with `--model m-2`
- **THEN** the command exits 1, names both models, and the model fake records no call

#### Scenario: A report with a case that the set lacks
- **WHEN** the report holds a case that the set of `--cases` does not hold
- **THEN** the command exits 1, names the case, and the model fake records no call

#### Scenario: A file that is not a report
- **WHEN** `--resume` names a JSON file with no model
- **THEN** the command exits 1 and names the file

## MODIFIED Requirements

### Requirement: The group lists the verify command
The command group `devops roadmap eval` SHALL list `verify`, with the options `--case`, `--model`, `--limit`, `--json`, `--dry-run`, `--cases`, `--source` and `--resume`.

#### Scenario: The command is found
- **WHEN** the user runs `devops roadmap eval --help`
- **THEN** the output lists `verify`
