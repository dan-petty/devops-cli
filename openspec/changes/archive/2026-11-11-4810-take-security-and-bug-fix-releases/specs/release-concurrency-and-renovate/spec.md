## ADDED Requirements

### Requirement: Renovate sets no minimum release age
`.github/renovate.json` SHALL hold no `minimumReleaseAge` and SHALL NOT extend `config:best-practices`, so that Renovate opens the pull request for a release with a security fix or a bug fix on the day it is published.

#### Scenario: The Renovate configuration is read
- **WHEN** a test reads `.github/renovate.json`
- **THEN** its text holds no `minimumReleaseAge`
- **AND** its `extends` list does not hold `config:best-practices`
