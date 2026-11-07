# research-advisories Specification

## Purpose
How `devops research advisories` finds the advisories that affect the pins of a repository: it asks OSV about the Python and Node packages of the inventory, reports each advisory with its severity, affected range and fixed version, and counts what it could not check, without a model.

## Requirements

### Requirement: Each advisory that affects a pin is a finding
`devops research advisories` SHALL ask OSV about each Python package and each Node package of the inventory that pins an exact version. It SHALL report one finding for each advisory that OSV returns for the version, and none for a version with no advisory. A finding SHALL hold the component, every `file:line` that pins it, the advisory id and aliases, the severity, the affected range, the fixed version and the summary.

#### Scenario: A pinned version inside an affected range
- **WHEN** OSV returns the advisory `GHSA-8q59-q68h-6hv4` for `pyyaml` 5.3
- **THEN** the report holds a finding for `pyyaml` 5.3 with that id, its aliases, the severity `CRITICAL`, the affected range `>=0 <5.4` and the fixed version `5.4`

#### Scenario: A version with no advisory
- **WHEN** OSV returns no advisory for `markupsafe` 2.1.5
- **THEN** the report holds no finding for `markupsafe`

#### Scenario: The reference tool agrees
- **WHEN** the command reads a repository whose `uv.lock` osv-scanner 2.6.0 has scanned
- **THEN** the set of package, version and advisory id of the findings equals the set that osv-scanner reports

#### Scenario: The order of the findings
- **WHEN** the report holds findings of the severities `MEDIUM` and `CRITICAL`
- **THEN** the finding of `CRITICAL` comes first, and findings of one severity follow in the order of name and advisory id

#### Scenario: The same pin in two files
- **WHEN** `pyproject.toml` and a requirement file pin `pyyaml` 5.3
- **THEN** OSV is asked about it once, and the finding lists both places

### Requirement: Only exact pins of packages are asked
The command SHALL send OSV the name, the version and the OSV ecosystem (`PyPI` or `npm`) of a package component. It SHALL NOT send a component whose version is empty or is not a version, and it SHALL count it in `unpinned`. It SHALL NOT send a tool of the tools lock, a container image, a chart, an action, a Terraform provider or a devcontainer feature, and it SHALL count each of them in `not_covered` under its ecosystem (`tool-lock-entry` for a tool whose package the lists hold).

#### Scenario: A pin that is a range
- **WHEN** `pyproject.toml` declares `pyyaml>=5.3` and `idna==3.6`
- **THEN** OSV is asked about `idna` only, and the summary counts one pin in `unpinned`

#### Scenario: Components that OSV cannot match
- **WHEN** the repository pins images, charts, actions and release binaries
- **THEN** none of them is in a query, and the summary counts each of them under its ecosystem

### Requirement: A lookup that fails is reported and is not clean
When OSV gives no answer for a package or for an advisory record, the report SHALL list a failure with the component, the advisory id when there is one, and the reason. The command SHALL print the report and then exit with code 1. A package whose lookup failed SHALL NOT appear as a package without findings.

#### Scenario: OSV answers 503
- **WHEN** the batch query gets the status 503
- **THEN** the report holds a failure for each package with the reason `OSV returned status 503`, no finding, and the command exits with code 1 after it prints the report

#### Scenario: One record cannot be read
- **WHEN** the record of one advisory gets the status 500 and the other records are read
- **THEN** the report holds the other findings and one failure that names the advisory

### Requirement: The command prints the report
The command SHALL print a table of the findings and a summary line, or with `--json` or `--format yaml` the findings, the failures and a summary with the count of components, queried package versions, package versions with findings, findings, unpinned pins, failures and components not covered. With `--dry-run` it SHALL list the requests it would send, send none, and have the dry-run class `request-plan`. Its MCP tool SHALL be read-only and take no argument.

#### Scenario: JSON output
- **WHEN** `devops research advisories --root <repository> --json` runs
- **THEN** the output is the JSON of the report for that repository

#### Scenario: Dry run
- **WHEN** `devops research advisories --root <repository> --dry-run` runs
- **THEN** the output lists the batch query and the record read, and no request reaches the network
