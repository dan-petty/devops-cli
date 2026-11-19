# ci-dependency-audit Specification Delta

## ADDED Requirements

### Requirement: Audit scans the tools lock requirement files
The `audit` row of `devops ci` and `devops ci audit` SHALL scan each Python requirement file under `src/devops_cli/tools_lock/` with `osv-scanner`.

#### Scenario: Audit scans each requirement file
- **WHEN** `devops ci audit` runs on a tools lock with `semgrep.txt`, `bandit.txt`, and `ansible-core.txt`
- **THEN** the audit calls `osv-scanner --lockfile requirements.txt:<file>` for each file and reports each file scanned

### Requirement: Audit fails on an advisory
`devops ci audit` SHALL fail when a requirement file of the tools lock holds a pin with a known advisory.

#### Scenario: A pin has an advisory
- **WHEN** a requirement file under `src/devops_cli/tools_lock/` contains a pin that `osv-scanner` reports with an advisory
- **THEN** `devops ci audit` exits non-zero and names the file, package, and advisory id

### Requirement: Tools lock finding with an active ignore entry passes
The `audit` row of `devops ci` and `devops ci audit` SHALL read `.osv-scanner-ignore.yaml`. An `osv-scanner` report of findings SHALL pass only when each of its advisories has an entry that names the requirement file of the audit and whose `expired_at` day has not come. The audit SHALL print each entry that it used, with its expiry and statement.

#### Scenario: Every advisory of the report is ignored
- **WHEN** `osv-scanner` reports advisories in `semgrep.txt` and an active entry names each advisory and file until a later day
- **THEN** the audit passes and prints each ignored advisory, the file, and the expiry day

#### Scenario: An ignore has expired
- **WHEN** `osv-scanner` reports a tools-lock advisory with no fixed version and its ignore expiry is before or on the run date
- **THEN** `devops ci audit` exits non-zero and reports the expired ignore

### Requirement: Semgrep release is named
If the pinned Semgrep version cannot take `mcp` 1.30.0 and `certifi` 2026.10.18, the change SHALL name the upstream release that blocks it.

#### Scenario: Upstream blocks the fix
- **WHEN** the pinned Semgrep version requires a version of a dependency that has no fix
- **THEN** the change notes that Semgrep upstream blocks the fix and adds a time-limited ignore for each advisory
