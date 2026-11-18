# ci-dependency-audit Specification

## Purpose
What the `audit` row of `devops ci` and `devops ci audit` pass and fail: the findings of `uv audit` and of `npm audit` on the lockfile of each Node tool, and the time-limited entries of `.npm-audit-ignore.yaml` for an advisory that no released version fixes.

## Requirements

### Requirement: An npm audit finding with an active ignore entry passes
The `audit` row of `devops ci` and `devops ci audit` SHALL read `.npm-audit-ignore.yaml`. An `npm audit` report of findings SHALL pass only when each of its advisories has an entry that names the lockfile of the audit and whose `expired_at` day has not come. The audit SHALL print each entry that it used, with its expiry and statement.

#### Scenario: Every advisory of the report is ignored
- **WHEN** `npm audit` of the OpenSpec lockfile reports only GHSA-fc5q-39xc-vjpf and an entry names that advisory and lockfile until a later day
- **THEN** the audit passes and prints the advisory, the lockfile and the expiry day

#### Scenario: One advisory has no entry
- **WHEN** the report holds an advisory that no active entry for its lockfile names
- **THEN** the audit fails as a finding

#### Scenario: An audit that could not run
- **WHEN** `npm audit` could not reach the registry
- **THEN** the audit fails as an audit that could not run, whatever the ignore file holds

### Requirement: An ignore entry expires on its day
An entry SHALL apply before its `expired_at` day and SHALL NOT apply on that day or later. The audit SHALL name each entry for its lockfile that expired.

#### Scenario: The expiry day comes
- **WHEN** the audit runs on the `expired_at` day of the only entry that covers its finding
- **THEN** the audit fails and says that the entry expired

### Requirement: An ignore entry is narrow and tracked
An entry SHALL name one advisory, each lockfile path, and a statement with the tracking issue as `#N`. The file SHALL refuse an entry with a wildcard in its ID or a path, with no path, or with no tracking issue.

#### Scenario: A wildcard entry
- **WHEN** an entry has the ID `GHSA-*`
- **THEN** reading the file fails

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
