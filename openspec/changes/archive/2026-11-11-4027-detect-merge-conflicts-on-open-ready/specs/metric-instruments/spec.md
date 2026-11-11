## MODIFIED Requirements

### Requirement: The row seconds histogram is declared and documented
`INSTRUMENTS` SHALL hold `devops_cli_roadmap_row_seconds` as a histogram with the unit `s` and the attributes `repo`, `row` and `result`. `docs/TELEMETRY.md` SHALL list it. One repository SHALL add at most 36 series: 12 rows x 3 results, and the buckets add no series.

#### Scenario: The registry and the document list the histogram
- **WHEN** a test reads `INSTRUMENTS` and `docs/TELEMETRY.md`
- **THEN** both list `devops_cli_roadmap_row_seconds`, and the registry gives the kind histogram and the unit `s`

#### Scenario: The series of one repository are bounded
- **WHEN** a test counts the rows of the due table and the results of a job
- **THEN** it finds 12 rows and 3 results
