# tools-lock-install Specification

## Purpose
The tools lock pins each tool at an exact version, and `devops install-tools` reports each tool whose command on PATH is not at its pin.

## Requirements

### Requirement: The check judges each tool by its link
`devops install-tools --check` SHALL report each tool whose commands in the target directory do not link to its locked version, SHALL exit 1 when it reports one, and SHALL make no request.

#### Scenario: A tool off its pin
- **WHEN** every tool of the lock but `k9s` and `semgrep` links to its locked version in the target directory and PATH is empty
- **THEN** the check names `k9s` and `semgrep`, exits 1 and makes no request, and exits 0 after both link to their locked versions
