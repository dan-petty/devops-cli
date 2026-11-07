# research-advisories Specification

## Purpose
How `devops research advisories` finds the advisories that affect the pins of a repository: it asks OSV about the Python and Node packages of the inventory, and GitHub about the Actions and the components that a watch list maps to a repository. It flags the CVEs of the CISA KEV list as exploited, reports each advisory with its severity, affected range and fixed version, and counts what it could not check, without a model.

## Requirements

### Requirement: Each advisory that affects a pin is a finding
`devops research advisories` SHALL ask OSV about each Python package and each Node package of the inventory that pins an exact version. It SHALL report one finding for each advisory that OSV returns for the version, and none for a version with no advisory. A finding SHALL hold the component, every `file:line` that pins it, the advisory id and aliases, the severity, the affected range, the fixed version, the summary, the source (`OSV` or `GitHub`) and the exploited flag.

#### Scenario: A pinned version inside an affected range
- **WHEN** OSV returns the advisory `GHSA-8q59-q68h-6hv4` for `pyyaml` 5.3
- **THEN** the report holds a finding for `pyyaml` 5.3 with that id, its aliases, the severity `CRITICAL`, the affected range `>=0 <5.4`, the fixed version `5.4` and the source `OSV`

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
The command SHALL send OSV the name, the version and the OSV ecosystem (`PyPI` or `npm`) of a package component with an exact version. It SHALL count a package whose version is empty or is not a version in `unpinned`, and SHALL NOT send it. It SHALL NOT send OSV a tool of the tools lock, an image, a chart, an action, a Terraform provider or a devcontainer feature.

#### Scenario: A pin that is a range
- **WHEN** `pyproject.toml` declares `pyyaml>=5.3` and `idna==3.6`
- **THEN** OSV is asked about `idna` only, and the summary counts one pin in `unpinned`

#### Scenario: Components that OSV cannot match
- **WHEN** the repository pins images and charts that the watch list does not map
- **THEN** none of them is in a query, and the summary counts each of them under its ecosystem

### Requirement: A component that no source matches is counted
The command SHALL count a component that no source matches in `not_covered` under its ecosystem (`tool-lock-entry` for a tool whose package the lists hold). It SHALL NOT count an Action or a mapped component there.

#### Scenario: Not covered
- **WHEN** the repository pins a chart and an image that the watch list does not map, and an Action
- **THEN** the summary counts the chart under `helm` and the image under `docker`, and does not count the Action

### Requirement: A lookup that fails is reported and is not clean
When OSV or GitHub gives no answer for a package, a repository or an advisory record, the report SHALL list a failure with the component, the advisory id when there is one, and the reason. The command SHALL print the report and then exit with code 1. A component whose lookup failed SHALL NOT appear as a component without findings.

#### Scenario: OSV answers 503
- **WHEN** the batch query gets the status 503
- **THEN** the report holds a failure for each package with the reason `OSV returned status 503`, no finding, and the command exits with code 1 after it prints the report

#### Scenario: One record cannot be read
- **WHEN** the record of one advisory gets the status 500 and the other records are read
- **THEN** the report holds the other findings and one failure that names the advisory

#### Scenario: GitHub answers an error
- **WHEN** the advisories of `qdrant/qdrant` get the status 500 and the Actions list gets the status 503
- **THEN** the report holds no finding and a failure for the chart and for each pinned Action, with the reasons `GitHub returned status 500` and `GitHub returned status 503`

### Requirement: The command prints the report
The command SHALL print a table of the findings, with an Exploited column, and a summary line. With `--json` or `--format yaml` it SHALL print the findings, the failures, the `kev_failure` and a summary of counts. With `--dry-run` it SHALL list the OSV, GitHub and KEV requests it would send, send none, and have the dry-run class `request-plan`. Its MCP tool SHALL be read-only and take no argument.

#### Scenario: JSON output
- **WHEN** `devops research advisories --root <repository> --json` runs
- **THEN** the output is the JSON of the report for that repository

#### Scenario: Dry run
- **WHEN** `devops research advisories --root <repository> --dry-run` runs
- **THEN** the output lists the batch query and the record read of OSV when a package is asked, the Actions request and the repository requests of GitHub, and the KEV list, and no request reaches the network

### Requirement: Each GitHub Action with an exact release is checked against the GitHub advisories
`devops research advisories` SHALL read the reviewed GitHub advisories that name each GitHub Action of the inventory whose version names one release (`GET /advisories` with the ecosystem `actions` and the package names), and SHALL report one finding for each advisory whose range holds the pinned version. An Action whose pin names no one release SHALL be counted in `unpinned` and SHALL NOT be sent.

#### Scenario: A pinned release inside an affected range
- **WHEN** a workflow pins `tj-actions/changed-files` at `v45.0.0` and GitHub lists the advisory `GHSA-mrrh-fwg8-r2c3` with the range `<= 45.0.7` and the fix 46.0.1
- **THEN** the report holds a finding with the source `GitHub`, the severity `HIGH`, the alias `CVE-2025-30066`, the affected range `<= 45.0.7` and the fixed version `46.0.1`

#### Scenario: A pinned release after the fix
- **WHEN** a workflow pins `tj-actions/changed-files` at `v46.0.1`
- **THEN** the report holds no finding for that pin

#### Scenario: A major tag
- **WHEN** a workflow pins `actions/checkout` at the tag `v4`
- **THEN** the pin is counted in `unpinned` and no advisory is matched to it

#### Scenario: A package name in the request
- **WHEN** the inventory holds the Actions `tj-actions/changed-files` and `actions/checkout`
- **THEN** one request names both packages in `affects`, and an advisory that names only one package is a finding for that package only

### Requirement: A watch list maps images, charts and release binaries to a repository
`.devops/research-watch.toml` SHALL map a component, by its ecosystem and name, to the GitHub repository `owner/name` that publishes its advisories. For each mapped component whose version names one release, the command SHALL read the advisories that the repository published (`GET /repos/{owner}/{repo}/security-advisories`) and report one finding for each advisory with a vulnerability whose range holds the version.

#### Scenario: The Qdrant server advisories
- **WHEN** the chart `qdrant` 1.19.1 is mapped to `qdrant/qdrant`, and that repository published `GHSA-3gph-6c29-p29v` (`>= 1.18.0, < 1.19.2`, fixed in 1.19.2) and `GHSA-frc7-44gm-99qq` (`< 1.20.0`, fixed in 1.20.0)
- **THEN** the report holds a finding with the source `GitHub` for each of the two advisories, and OSV is not asked

#### Scenario: A vulnerability of another range
- **WHEN** the repository also published an advisory with the range `>= 1.9.3, < 1.15.6`
- **THEN** the report holds no finding for that advisory

#### Scenario: No watch list file
- **WHEN** the repository has no `.devops/research-watch.toml`
- **THEN** the watch list is empty and no repository is read

#### Scenario: A component that is not mapped
- **WHEN** the repository pins a chart that the watch list does not map
- **THEN** no request names it, and the summary counts it in `not_covered` under `helm`

### Requirement: An entry of the watch list may name the package of the advisories
An entry MAY name the `package` that the advisories of the repository give to the component. With a `package`, the command SHALL count only the vulnerabilities that name it, and without one it SHALL count every vulnerability of an advisory.

#### Scenario: Two modules in one advisory
- **WHEN** an advisory lists `example.com/app/v2` with the range `>= 2.7.0` and `example.com/app/v3` with the range `>= 3.0.0, < 3.5.4`, and the pinned release is 3.5.4
- **THEN** the entry with the package `example.com/app/v3` gives no finding, and the entry with no package gives one

### Requirement: The watch list is checked
Reading the watch list SHALL be an error that names the file when it is not valid TOML, has an unknown key, has a repository that is not `owner/name`, or maps a Python package, a Node package or an Action. An entry for a release binary of `tools.lock` SHALL name the repository of its `source`, and a binary that has no entry SHALL be named as left out in the watch list file.

#### Scenario: A file that is wrong
- **WHEN** an entry has the repository `qdrant`, an unknown key, or the ecosystem `pypi`
- **THEN** reading the watch list is an error that names `.devops/research-watch.toml`

#### Scenario: The binaries of the tools lock
- **WHEN** the watch list of this repository is read
- **THEN** each binary of `tools.lock` maps, as a `github-release` component, to the repository of its `source`, except the binaries that the file names as left out

### Requirement: The range of an advisory is matched with packaging
The command SHALL match a pinned version to the range of a GitHub advisory (`<= 45.0.7`, `< 41`, `>= 1.18.0, < 1.19.2`, `= 1.2.3`) with `packaging`; ranges that `||` joins match when any of them holds. A pin names one release only when it has at least three numbers after an optional `v`. A range that is empty or that cannot be read SHALL be a failure that names the advisory, and SHALL NOT be a pin that is clean.

#### Scenario: The edge of a range
- **WHEN** the pinned version is `45.0.7` and the range is `<= 45.0.7`, or the version is `41.0.0` and the range is `< 41`
- **THEN** the first is in the range and the second is not

#### Scenario: Ranges joined with ||
- **WHEN** the range is `>= 3.0.0, < 3.3.15 || >= 3.4.0, < 3.4.10 || >= 3.5.0, < 3.5.4`
- **THEN** `3.5.3` is in the range and `3.5.4` is not

#### Scenario: A range that cannot be read
- **WHEN** an advisory of a mapped repository has the range `since the start`
- **THEN** the report holds no finding for it and holds a failure that names the advisory

### Requirement: A CVE in the CISA KEV list sets the exploited flag
The command SHALL read the CISA Known Exploited Vulnerabilities list once, when at least one finding names a CVE in its id or aliases, and SHALL set `exploited` to true on each finding with a CVE in the list. It SHALL send no request to the list when no finding names a CVE. A list that cannot be read SHALL be `kev_failure` in the report, no finding SHALL be flagged, and the command SHALL print the report and exit with code 1.

#### Scenario: An exploited CVE
- **WHEN** a finding has the alias `CVE-2025-30066` and the list holds it
- **THEN** the finding has `exploited` true, the table shows `yes` in the Exploited column, and the summary counts one exploited finding

#### Scenario: A finding with no CVE
- **WHEN** the findings are the Qdrant advisories, which have no CVE
- **THEN** no request goes to `www.cisa.gov`

#### Scenario: The list cannot be read
- **WHEN** `www.cisa.gov` answers 503
- **THEN** the report holds the findings with `exploited` false and `kev_failure` set to `CISA KEV returned status 503`, and the command exits with code 1
