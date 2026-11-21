## ADDED Requirements

### Requirement: The runner image holds the scanners of a review
The runner image SHALL hold Gitleaks, Pluto, osv-scanner, golangci-lint and Semgrep from the devtools image, at the versions of the installed tools. Each of the five SHALL be an entry of `RUNNER_TOOLS` with the source `ToolSource.DEVTOOLS` and SHALL NOT be an entry of `NOT_IN_RUNNER`. Each binary of the analyzer table of the review SHALL be an entry of `RUNNER_TOOLS`.

#### Scenario: Each added scanner in the table
- **WHEN** the runner tool table is read after the change
- **THEN** Gitleaks, Pluto, osv-scanner, golangci-lint and Semgrep are entries of `RUNNER_TOOLS`, and none of the five is an entry of `NOT_IN_RUNNER`

#### Scenario: Each analyzer binary in the table
- **WHEN** the runner tool table is read after the change
- **THEN** each binary of `STATIC_ANALYZERS` is an entry of `RUNNER_TOOLS`
