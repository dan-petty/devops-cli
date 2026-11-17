## ADDED Requirements

### Requirement: The runner image holds the scanners of a review
The runner image SHALL hold Gitleaks 8.30.1, Pluto 5.24.4, osv-scanner 2.6.0 and golangci-lint 1.64.8 from `src/devops_cli/tools_lock/tools.lock`, and Semgrep 1.179.0 from `src/devops_cli/tools_lock/semgrep.txt`. Each of the five SHALL be an entry of `RUNNER_TOOLS` and SHALL NOT be an entry of `NOT_IN_RUNNER`. `kubectl` and `kube-linter` SHALL stay out of the runner image, because #3562 and #5394 own them.

#### Scenario: Each added scanner in the table
- **WHEN** the runner tool table is read after the change
- **THEN** Gitleaks, Pluto, osv-scanner, golangci-lint and Semgrep are entries of `RUNNER_TOOLS` at their lock versions, and none of the five is an entry of `NOT_IN_RUNNER`

#### Scenario: The cluster tools stay out
- **WHEN** the runner tool table is read after the change
- **THEN** `kubectl` and `kube-linter` are entries of `NOT_IN_RUNNER`
