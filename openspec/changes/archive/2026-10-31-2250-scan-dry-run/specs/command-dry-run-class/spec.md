# Spec Delta: command-dry-run-class for Scan Commands

## Added Requirements

### Requirement: scan-request-plans
Five commands in `scan` SHALL carry the `request-plan` dry-run class: `scan` (callback), `scan trivy`, `scan fix`, `scan report`, and `scan sast`.
Under dry run, each command SHALL make zero external requests, execute zero subprocesses, and output its planned requests.

#### Scenario: Dry run on scan trivy
- **WHEN** user executes `devops scan trivy --dry-run`
- **THEN** the command prints planned Trivy scan requests and starts no process

#### Scenario: Dry run on scan sast
- **WHEN** user executes `devops scan sast --dry-run`
- **THEN** the command prints planned Semgrep scan requests and starts no process

#### Scenario: Dry run on scan report
- **WHEN** user executes `devops scan report --dry-run`
- **THEN** the command prints planned scanner suite requests and starts no process

#### Scenario: Dry run on scan fix
- **WHEN** user executes `devops scan fix --dry-run`
- **THEN** the command prints planned OSV query and remediation requests and starts no process

### Requirement: scan-no-external-request
Seven local scan commands SHALL carry the `no-external-request` dry-run class: `scan aibom`, `scan complexity`, `scan injection`, `scan sarif`, `scan sbom`, `scan secrets`, and `scan workflows`.
Under `devops --dry-run`, each command SHALL execute locally without external network requests.
Echo-only previews and explicit `--dry-run` options SHALL be removed from read-only commands without a shim.

#### Scenario: Dry run on scan complexity
- **WHEN** user executes `devops --dry-run scan complexity`
- **THEN** the command renders local complexity analysis without echo-only preview

#### Scenario: Dry run on scan workflows
- **WHEN** user executes `devops --dry-run scan workflows`
- **THEN** the command executes local workflow audit without external requests
