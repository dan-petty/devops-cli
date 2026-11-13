## MODIFIED Requirements

### Requirement: The row seconds histogram is declared and documented
`INSTRUMENTS` SHALL hold `devops_cli_roadmap_row_seconds` as a histogram with the unit `s` and the attributes `repo`, `row` and `result`, and `lane` in a round of the Service. `docs/TELEMETRY.md` SHALL list it. One repository SHALL add at most 39 series: 13 rows x 3 results, because each row is in one lane only, and the buckets add no series.

#### Scenario: The registry and the document list the histogram
- **WHEN** a test reads `INSTRUMENTS` and `docs/TELEMETRY.md`
- **THEN** both list `devops_cli_roadmap_row_seconds`, and the registry gives the kind histogram and the unit `s`

#### Scenario: The series of one repository are bounded
- **WHEN** a test counts the rows of the due table and the results of a job
- **THEN** it finds 13 rows and 3 results

### Requirement: Each row that ran adds its seconds
A round of the roadmap SHALL send one sample of `devops_cli_roadmap_row_seconds` for each row that ran, with the seconds of its runner and the attributes `repo`, `row` and `result`, and `lane` when the round has a lane. The `result` SHALL be `success`, `error` or `stopped`, with the same meaning as in `devops_cli_service_jobs_total`. A row that is not due, a row that the failure ledger suspends and a row that a clone failure keeps from running SHALL add no sample.

#### Scenario: Two rows run
- **WHEN** a round of the lane `status` runs the rows `metrics` and `implement`, and the first takes 2.5 seconds and the second 7 seconds
- **THEN** the collector receives one sample of 2.5 seconds with `row` `metrics` and `result` `success`, and one of 7 seconds with `row` `implement` and `result` `success`, each with the attribute `repo` and the attribute `lane` `status`

#### Scenario: A row is not due or is suspended
- **WHEN** a round has a row that no trigger makes due, and a row that failed its limit of rounds on the same input
- **THEN** neither row adds a sample in that round

#### Scenario: A clone failure keeps a row from running
- **WHEN** the clone of the repository fails and the rows of the round need it
- **THEN** no runner is called and the histogram receives no sample

#### Scenario: A row raises
- **WHEN** a row takes 4 seconds and then raises an error
- **THEN** the collector receives a sample of 4 seconds with `result` `error`, and with `result` `stopped` when the error is the stop of the Service

#### Scenario: A run with no lane
- **WHEN** a run with no lane, such as one of the command line, runs a row
- **THEN** the collector receives the sample of that row with no attribute `lane`
