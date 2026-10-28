## ADDED Requirements

### Requirement: uv audit audits the lockfile as it is
The uv audit adapter SHALL start `uv audit --frozen --quiet --output-format json` in the directory that it scans, so that uv audits the `uv.lock` of the project as it is and does not write it.

#### Scenario: The adapter scans a project directory
- **WHEN** the uv audit adapter scans a project directory
- **THEN** uv starts in that directory with `uv audit --frozen --quiet --output-format json`

### Requirement: uv audit reports each finding of its report
The uv audit adapter SHALL give one finding for each vulnerability of the JSON report of uv, at `uv.lock:<package>`, with the advisory id and the summary in its title and the releases that fix it in its fix. It SHALL give one finding for each adverse project status of the report.

#### Scenario: uv audit finds vulnerabilities and adverse statuses
- **WHEN** uv audit exits 1 and reports a vulnerability of urllib3 1.26.5 that the releases 1.26.19 and 2.2.2 fix, a vulnerability `PYSEC-2024-60` of idna 3.6 with no summary and no fix release, and the adverse statuses `archived` of `legacy-lib` and `quarantined` of `suspect-lib`
- **THEN** the outcome is `ran` with four findings at the severity `MEDIUM`: the fix of the first is `Upgrade urllib3 from 1.26.5 to 1.26.19 or 2.2.2`, the title of the second is `[PYSEC-2024-60] idna 3.6 has a known vulnerability`, and the titles of the last two are `[archived] legacy-lib is archived on its index` and `[quarantined] suspect-lib is quarantined on its index`

#### Scenario: uv audit finds nothing
- **WHEN** uv audit exits 0 with a report of no vulnerability and no adverse status
- **THEN** the outcome is `ran` with no finding

### Requirement: A uv audit run with no project report is a failed scan
The uv audit adapter SHALL read a run that writes no report and exits non-zero as a failed scan, with what uv wrote on stderr as the reason. It SHALL read a report with no `vulnerabilities` list or no `adverse_statuses` list as a failed scan, and not as a scan that found nothing.

#### Scenario: The project has no lockfile
- **WHEN** uv audit exits 1, writes no report, and writes "error: Unable to find lockfile at `uv.lock`" and the rest of its message on stderr
- **THEN** the outcome is `failed`, with a reason that is `Scanner exited with code 1:` and then the message of uv

#### Scenario: The report has another layout
- **WHEN** uv audit exits 0 and writes a report with no `vulnerabilities` list and no `adverse_statuses` list
- **THEN** the outcome is `failed` with no finding, and its reason starts with `Scanner execution failed:`

### Requirement: uv audit scans only a directory
The uv audit adapter SHALL NOT start uv for a path that is not a directory, such as a directory that does not exist or a file. It SHALL give the outcome `not_applicable` with a reason that names the path, so that uv does not audit the project of a parent directory as the project of that path.

#### Scenario: The directory does not exist
- **WHEN** the uv audit adapter scans the path `services/api-typo` of a project, and no directory is at that path
- **THEN** uv does not start, and the outcome is `not_applicable` with no finding and the reason `<path> is not a directory. uv audit audits the project of a directory.`

#### Scenario: The path is a file
- **WHEN** the uv audit adapter scans the `uv.lock` file of a project
- **THEN** uv does not start, and the outcome is `not_applicable` with no finding and the reason `<path> is not a directory. uv audit audits the project of a directory.`
