# Spec Delta

## MODIFIED Requirements

### Requirement: A scan command reports a scan that gave no result as not run
`devops scan trivy`, `devops scan sast` and `devops scan secrets` SHALL report a scan whose outcome status is in `CONST_SCAN_NO_RESULT_STATUSES` as not run, with its reason, and SHALL NOT say that the scan passed. The MCP tools `scan_trivy`, `scan_sast` and `scan_secrets` run these commands. The JSON and YAML output of these commands SHALL hold the status and the reason of the scan next to the findings, and a scan that gave no result SHALL NOT print only an empty findings list.

#### Scenario: Gitleaks is not installed
- **WHEN** no directory of PATH holds Gitleaks, and `devops scan secrets <directory>` runs
- **THEN** the command exits 0, and its last line is `! Gitleaks was not run (Binary 'gitleaks' not found on PATH).`

#### Scenario: Gitleaks is not installed with JSON output
- **WHEN** no directory of PATH holds Gitleaks, and `devops scan secrets <directory> --json` runs
- **THEN** the command exits 0, and the JSON output is a dictionary with `status` `"not installed"`, `reason` `"Binary 'gitleaks' not found on PATH"`, and `findings` `[]`

#### Scenario: Clean scan with JSON output
- **WHEN** Semgrep runs and finds no flaws, and `devops scan sast <directory> --json` runs
- **THEN** the command exits 0, and the JSON output is a dictionary with `status` `"ran"`, `reason` `""`, and `findings` `[]`
