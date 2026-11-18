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
