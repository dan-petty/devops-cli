## ADDED Requirements

### Requirement: The runner image holds the scanners of a review
The runner image SHALL hold Gitleaks, Pluto, osv-scanner, golangci-lint and Semgrep from the devtools image, at the versions of the installed tools. Each of the five SHALL be an entry of `RUNNER_TOOLS` with the source `ToolSource.DEVTOOLS` and SHALL NOT be an entry of `NOT_IN_RUNNER`. `kubectl` and `kube-linter` SHALL stay out of the runner image, because #3562 and #5394 own them.

#### Scenario: Each added scanner in the table
- **WHEN** the runner tool table is read after the change
- **THEN** Gitleaks, Pluto, osv-scanner, golangci-lint and Semgrep are entries of `RUNNER_TOOLS` at their lock versions, and none of the five is an entry of `NOT_IN_RUNNER`

#### Scenario: The cluster tools stay out
- **WHEN** the runner tool table is read after the change
- **THEN** `kubectl` and `kube-linter` are entries of `NOT_IN_RUNNER`
