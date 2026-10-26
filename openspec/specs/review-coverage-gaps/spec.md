# review-coverage-gaps Specification

## Purpose
How a review of `devops review path`, `branch` or `pr` states each file that one of its stages could not read: the report names the file, the stage and the reason as a coverage gap. A file that the review reads but cannot parse is no coverage gap.

## Requirements

### Requirement: A file that pre-analysis cannot read is a coverage gap of the review
Pre-analysis SHALL give no metadata for a file that it cannot read, and the review SHALL record the file as a coverage gap with the reason `Pre-analysis: <error>`. The table of skipped and errored files of the report SHALL give that row.

#### Scenario: A file with no read permission
- **WHEN** pre-analysis runs on two files of a project and the user cannot read one of them
- **THEN** pre-analysis gives the metadata of the other file only
- **AND** the report's table of skipped and errored files has the row `| <file> | Pre-analysis: Permission denied |`

### Requirement: Pre-analysis gives metadata for a Python file that the ast module cannot parse
Pre-analysis SHALL give metadata for a Python file that it reads and that the `ast` module cannot parse, because of a syntax error or an expression too deep for the parse. The symbols of the metadata SHALL come from the text of the file. Such a file SHALL be no coverage gap.

#### Scenario: A Python file with an expression of 200,000 terms
- **WHEN** pre-analysis runs on a Python file that defines the function `deep` and holds an expression of 200,000 chained `+ a` terms
- **THEN** the metadata of the file has the key symbol `deep`
- **AND** the report has no table of skipped and errored files

### Requirement: A scanner finding in a file that admission cannot read is a coverage gap
Admission SHALL reject a scanner finding whose cited file it cannot read, because it cannot check the finding against the lines of the file. The review SHALL record the file as a coverage gap with the reason `Admission: <error>`.

#### Scenario: A Bandit finding in a file with no read permission
- **WHEN** Bandit reports a finding at a line of a file that the user cannot read
- **THEN** the payload of the file holds no finding
- **AND** the report's table of skipped and errored files has the row `| <file> | Admission: Permission denied |`

### Requirement: A file that the threat-intelligence lookup cannot read is a coverage gap
A review with threat intelligence SHALL record each file whose network references it cannot read as a coverage gap with the reason `Threat intelligence: <error>`.

#### Scenario: A file with no read permission
- **WHEN** a review with threat intelligence builds the payload of a file that the user cannot read
- **THEN** the report's table of skipped and errored files has the row `| <file> | Threat intelligence: Permission denied |`

### Requirement: Cached metadata whose time cannot be compared is a cache miss
Pre-analysis SHALL analyze a file again when the time of its cached metadata does not parse or has no time zone.

#### Scenario: A cached time with no time zone or that does not parse
- **WHEN** a review of a path runs pre-analysis on files whose cached metadata has the time `2026-01-01T00:00:00` or `not a time`
- **THEN** pre-analysis analyzes each file again and reuses no cached metadata

### Requirement: A base revision file that cannot be read is a coverage gap
A review SHALL record each base revision file that it cannot read as a coverage gap with the reason `Base revision: <error>`. A base revision file that does not exist SHALL NOT be a coverage gap.

#### Scenario: A base revision file read fails from GitHub
- **WHEN** a pull request review reads a base revision file and the GitHub API returns an error
- **THEN** the review records the file as a coverage gap with the reason `Base revision: <error>`
- **AND** the review continues scanning the remaining candidate files
