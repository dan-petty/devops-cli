# review-tool-databases Specification

## Purpose
A review runs osv-scanner and Trivy in a sandbox with no network, and the sandbox binds their databases read-only. `devops review fetch-databases` is the one step that fetches these databases, outside the sandbox, and a review that lacks a database or finds it old says so as a coverage gap that names that command.

## Requirements

### Requirement: One command fetches the databases that the sandbox binds
`devops review fetch-databases [PATH]` SHALL start osv-scanner with `--download-offline-databases` over the lockfiles of `PATH`, and Trivy with `--download-db-only` and `trivy config` over an empty directory, outside the sandbox. Each tool SHALL get the variable and the directory of the `data_dirs()` of its scanner. A failure of one tool SHALL NOT skip the other.

#### Scenario: Both databases are fetched into the bound directories
- **WHEN** `PATH` holds a lockfile and the user runs the command
- **THEN** the command starts osv-scanner with `OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY` set to the directory of `OsvScanner.data_dirs()` and Trivy with `TRIVY_CACHE_DIR` set to the directory of `TrivyScanner.data_dirs()`
- **AND** the command reports each database and its directory

#### Scenario: A vulnerable lockfile is a successful fetch
- **WHEN** osv-scanner exits with code 1 because the lockfile has a vulnerable package
- **THEN** the fetch of osv-scanner succeeded
- **AND** any other exit code of osv-scanner, and any exit code of Trivy other than 0, fails the command with the error of the tool

#### Scenario: A tree with no lockfile
- **WHEN** `PATH` holds no lockfile
- **THEN** the command starts no osv-scanner fetch and says that no ecosystem was found
- **AND** the Trivy fetch still runs

#### Scenario: One fetch fails
- **WHEN** the Trivy fetch exits with code 1
- **THEN** the osv-scanner fetch has still run
- **AND** the command exits with code 1 and shows the error of Trivy

#### Scenario: A dry run
- **WHEN** the user runs the command with `--dry-run`
- **THEN** the command lists the commands and the directories it would use and starts no process

### Requirement: A fetch renews the age of the databases it confirmed
After the osv-scanner fetch, the command SHALL set the modified time of `<ecosystem>/all.zip` to now for each ecosystem in the report of osv-scanner, so that a database that upstream did not change is current.

#### Scenario: An unchanged database
- **WHEN** the fetch finds the database of PyPI unchanged and its file is two days old
- **THEN** the file is current after the fetch

### Requirement: A scan that lacks a database is a coverage gap that names the command
A run of osv-scanner that stops with `no offline version of the OSV database is available`, and a run of Trivy that stops with `failed to download vulnerability DB`, SHALL give the outcome `coverage_gap` with no finding and a reason that names `devops review fetch-databases`.

#### Scenario: osv-scanner has no database
- **WHEN** osv-scanner exits with the error that no offline version of the database is available
- **THEN** the outcome is a coverage gap
- **AND** the reason names `devops review fetch-databases`

#### Scenario: Trivy has no database
- **WHEN** Trivy exits with the error that it failed to download the vulnerability DB
- **THEN** the outcome is a coverage gap
- **AND** the reason names `devops review fetch-databases`

### Requirement: An old osv-scanner database is a coverage gap that keeps the findings
A run of osv-scanner that read the database of an ecosystem in its report, where the file is older than 24 hours, SHALL give the outcome `coverage_gap` with the findings of the run and a reason that names the ecosystems and `devops review fetch-databases`. A database of an ecosystem that is not in the report SHALL NOT make a gap.

#### Scenario: An old database
- **WHEN** osv-scanner ran over a PyPI lockfile and `PyPI/all.zip` is 25 hours old
- **THEN** the outcome is a coverage gap with the findings of the run
- **AND** the reason names `PyPI` and `devops review fetch-databases`

#### Scenario: An old database of another ecosystem
- **WHEN** osv-scanner ran over a PyPI lockfile, `PyPI/all.zip` is current and `npm/all.zip` is 25 hours old
- **THEN** the outcome is `ran`

### Requirement: osv-scanner is named only files that it reads as lockfiles
The lockfiles of a tree, for the scan of osv-scanner and for its fetch, SHALL be the files that git lists whose name is in `CONST_LOCKFILE_NAMES`. A file whose name only ends in `.lock`, such as `rules.lock`, SHALL NOT be named to osv-scanner.

#### Scenario: A file that ends in .lock
- **WHEN** a tree holds `uv.lock` and `rules.lock`
- **THEN** the scan and the fetch name `uv.lock` alone

### Requirement: The review lockfile bucket holds known lockfile names only
The review pipeline SHALL place a file in the osv-scanner lockfile bucket only when the file's name is in `CONST_LOCKFILE_NAMES`. A file that only ends in `.lock` or `.lockb`, such as `rules.lock` or `tools.lock`, SHALL NOT reach the bucket, from the reviewed files or from the lockfiles beside them.

#### Scenario: rules.lock and tools.lock are excluded
- **WHEN** the classifier receives `src/devops_cli/review/rules/rules.lock`, `src/devops_cli/tools_lock/tools.lock` and `uv.lock`
- **THEN** the lockfile bucket holds `uv.lock` and holds neither `rules.lock` nor `tools.lock`

#### Scenario: A lockfile beside a reviewed file is a known name
- **WHEN** a reviewed file sits in a directory that holds `uv.lock` and `rules.lock`
- **THEN** the lockfile bucket holds `uv.lock` alone
