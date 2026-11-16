## ADDED Requirements

### Requirement: A security fix of this repository merges itself after the required checks
The `vulnerabilityAlerts` object of `.github/renovate.json` SHALL set `automerge: true`, `automergeType: pr` and `platformAutomerge: true`, for each update type, so GitHub merges a security fix only after the required checks of the ruleset `main` pass. No other part of `.github/renovate.json` and no part of `.github/renovate/base.json` SHALL turn automerge on.

#### Scenario: The automerge scope
- **WHEN** a test reads `.github/renovate.json` and `.github/renovate/base.json`
- **THEN** the one `automerge: true` is `vulnerabilityAlerts.automerge` of `.github/renovate.json`, with GitHub auto-merge and no update-type filter
