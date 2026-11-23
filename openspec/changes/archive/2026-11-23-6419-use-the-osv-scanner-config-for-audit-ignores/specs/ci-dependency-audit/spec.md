# ci-dependency-audit Specification Delta

## MODIFIED Requirements

### Requirement: An npm audit finding with an active ignore entry passes
The `audit` row of `devops ci` and `devops ci audit` SHALL read `osv-scanner.toml`. An `osv-scanner` finding SHALL pass when an active `[[IgnoredVulns]]` entry names its advisory ID until a later day.

#### Scenario: Every advisory of the report is ignored
- **WHEN** `npm audit` of the OpenSpec lockfile reports only GHSA-fc5q-39xc-vjpf and an entry names that advisory and lockfile until a later day
- **THEN** the audit passes and prints the advisory, the lockfile and the expiry day

#### Scenario: One advisory has no entry
- **WHEN** the report holds an advisory that no active entry for its lockfile names
- **THEN** the audit fails as a finding

#### Scenario: An audit that could not run
- **WHEN** `npm audit` could not reach the registry
- **THEN** the audit fails as an audit that could not run, whatever the ignore file holds

#### Scenario: Native ignore config filters findings
- **WHEN** `osv-scanner` audits the root lockfile and `osv-scanner.toml` holds an active ignore entry for a finding
- **THEN** `osv-scanner` exits 0 and the audit row passes

### Requirement: An ignore entry expires on its day
An ignore entry SHALL apply before its expiry day and SHALL NOT apply on that day or later.

#### Scenario: The expiry day comes
- **WHEN** the audit runs on the `expired_at` day of the only entry that covers its finding
- **THEN** the audit fails and says that the entry expired

#### Scenario: An osv-scanner ignore entry reaches its expiry
- **WHEN** an entry in `osv-scanner.toml` reaches its `effectiveUntil` date
- **THEN** `osv-scanner` reports the vulnerability and exits 1

### Requirement: An ignore entry is narrow and tracked
An entry in `osv-scanner.toml` SHALL name one advisory, an `effectiveUntil` date, and a `reason` with the tracking issue as `#N`. Pre-commit schema validation SHALL refuse an entry with a wildcard in its ID, with no expiry, or with no tracking issue.

#### Scenario: A wildcard entry
- **WHEN** an entry has the ID `GHSA-*`
- **THEN** reading the file fails

#### Scenario: Missing reason or wildcard in native config is refused
- **WHEN** `check-jsonschema` validates an `osv-scanner.toml` with a wildcard id or missing reason
- **THEN** pre-commit validation fails

### Requirement: Audit reads the root npm lockfile
The `audit` row of `devops ci` and `devops ci audit` SHALL run `osv-scanner scan source --lockfile package-lock.json` over the `package-lock.json` at the root, which pins OpenSpec and Style Dictionary.

#### Scenario: The audit row names the root lockfile
- **WHEN** a test reads the commands of the `audit` check
- **THEN** they hold `npm audit --package-lock-only --json --no-update-notifier --prefix .` after `uv audit`

#### Scenario: An ignore of the root lockfile applies
- **WHEN** `npm audit` of the root lockfile reports only GHSA-fc5q-39xc-vjpf and an entry names that advisory and `package-lock.json` until a later day
- **THEN** the audit passes and names the ignored advisory

#### Scenario: The audit row runs osv-scanner over the root lockfile
- **WHEN** a test reads the commands of the `audit` check
- **THEN** they hold `osv-scanner scan source --lockfile package-lock.json` after `uv audit`
