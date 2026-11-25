## ADDED Requirements

### Requirement: The map covers the guideline rows
The row-check map MUST hold exactly one entry for each row id of `docs/guidelines/production-readiness.md`, with that row's Level and Scope.

#### Scenario: A missing or an unknown row id
- **WHEN** A test parses the row ids, Level cells and Scope cells of `docs/guidelines/production-readiness.md` and compares them with the row-check map.
- **THEN** Each row id has one entry with the same level and scope, and a missing or unknown row id fails the test with its id.

### Requirement: The map check matches the Measured by cell
Each row-check map entry MUST name the same tool checks and commands as the Measured by cell of its guideline row.

#### Scenario: A changed Measured by cell
- **WHEN** A test parses each Measured by cell of `docs/guidelines/production-readiness.md` and compares its tool checks and commands with the entry of the same row id.
- **THEN** Each cell matches its entry, and a changed cell fails the test with the row id.

### Requirement: The map holds no issue number and no gap table
The row-check map MUST hold no issue number and no gap table.

#### Scenario: An issue number in the map
- **WHEN** A test scans each row-check map entry for an issue reference or a gap table field.
- **THEN** No entry holds an issue reference or a gap table field.

### Requirement: Scorecard JSON maps to row states
The readiness reader MUST map each Scorecard check in a recorded JSON result to the row that it measures and to that row's state.

#### Scenario: A recorded Scorecard JSON result
- **WHEN** A test gives the reader a recorded Scorecard JSON result of one repository.
- **THEN** The report gives each row that a Scorecard check measures a state of met, partly met or not met, and the check name as its source.

### Requirement: The Scorecard reader runs the pinned binary
The Scorecard reader MUST run the pinned OpenSSF Scorecard binary with `--format json` once for each repository of the live setting `service.repos` and once for each infra repository of the setting `infra.repos`.

#### Scenario: Two repositories in settings
- **WHEN** A test runs the Scorecard reader with two repositories in `service.repos`, one repository in `infra.repos` and a process edge that records the argv.
- **THEN** The recorded argv holds one Scorecard run with `--format json` for each of the two repositories and for the infra repository.

### Requirement: File rows use the GitHub contents query
The report MUST read a row whose check is a file on the default branch with the GitHub reader of #4692 and a contents query at the ref.

#### Scenario: A file row
- **WHEN** A test runs the report with a fake GitHub reader for a row whose check is `AGENTS.md`, `CODEOWNERS` or `openspec/config.yaml`.
- **THEN** The fake reader receives a contents query for that path at the ref, and the row holds the reader's state, source and read time.

### Requirement: Command rows run the devops command
The report MUST run a row whose check is a `devops` command with its JSON output at the ref and map the JSON result to the row state.

#### Scenario: A command row
- **WHEN** A test runs the report for a row whose check is `devops repos onboard --plan` and a process edge that records the argv and returns a JSON result.
- **THEN** The recorded argv holds that command with its JSON output, and the row holds the state of the JSON result, with the command as its source.

### Requirement: A manual row gets no request
The report MUST give a row whose check is `manual` the state `not readable` and MUST send no request for it.

#### Scenario: A manual row
- **WHEN** A test runs the report for a repository that has a row whose check is `manual` and a reader that counts requests.
- **THEN** The row holds the state `not readable` and the counter shows no request for it.

### Requirement: Each row gives its state, source and read time
The report MUST give each row one state, the source of the value and the time of the read.

#### Scenario: A readable row
- **WHEN** A test runs the readiness report for one repository.
- **THEN** Each row holds one state, the source of the value and the read time.

### Requirement: The ref option reads the branch
The `--ref` option MUST read the repository rows at the named branch.

#### Scenario: A branch differs from the default branch
- **WHEN** A test runs the readiness report with `--ref` at a branch whose files differ from the default branch.
- **THEN** The report gives the states of the branch files and not the states of the default branch.

### Requirement: Private repository rows stay out of the shared report
The report MUST keep the rows of a private repository out of the shared report.

#### Scenario: A private repository
- **WHEN** A test gives the report a repository that the GitHub API reports as private.
- **THEN** The shared report holds no row of that repository.

### Requirement: A private repository falls back to the GitHub API
When the pinned Scorecard binary cannot read a private repository, the report MUST read that repository's practice rows with the GitHub API reader of #4692 and name that reader as their source.

#### Scenario: Scorecard refuses a private repository
- **WHEN** A test makes the Scorecard reader fail for a repository that the GitHub API reports as private.
- **THEN** The report reads the practice rows with the GitHub API reader and each row names the GitHub reader as its source.

### Requirement: The dry run sends no request
The `--dry-run` option MUST send no request.

#### Scenario: A dry run with a request counter
- **WHEN** A test runs the readiness report with `--dry-run` and a reader that counts requests.
- **THEN** The counter stays at zero and the report lists the planned reads.

### Requirement: The report reads the repository names from settings
The report MUST take the repository names from the live setting `service.repos` at run time.

#### Scenario: A changed repository list
- **WHEN** A test sets `service.repos` to a list and runs the report.
- **THEN** The report reads exactly the repositories of that list, and no committed file of the change holds a repository name of the setting.

### Requirement: The guideline states the record use
`docs/guidelines/production-readiness.md` MUST say that the readiness report holds the record of a running service and, with `--ref`, of a launch.

#### Scenario: The readiness record section
- **WHEN** A test reads the readiness record section of `docs/guidelines/production-readiness.md`.
- **THEN** It holds a sentence that the readiness report is the record of a running service and, with `--ref`, of a launch.
