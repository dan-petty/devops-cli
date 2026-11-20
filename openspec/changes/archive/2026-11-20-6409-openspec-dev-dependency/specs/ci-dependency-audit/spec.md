## ADDED Requirements

### Requirement: Audit reads the root npm lockfile
The `audit` row of `devops ci` and `devops ci audit` SHALL run `npm audit --package-lock-only --json --no-update-notifier --prefix .` over the `package-lock.json` at the root, which pins OpenSpec and Style Dictionary, and an entry of `.npm-audit-ignore.yaml` SHALL name that lockfile as `package-lock.json`.

#### Scenario: The audit row names the root lockfile
- **WHEN** a test reads the commands of the `audit` check
- **THEN** they hold `npm audit --package-lock-only --json --no-update-notifier --prefix .` after `uv audit`

#### Scenario: An ignore of the root lockfile applies
- **WHEN** `npm audit` of the root lockfile reports only GHSA-fc5q-39xc-vjpf and an entry names that advisory and `package-lock.json` until a later day
- **THEN** the audit passes and names the ignored advisory
