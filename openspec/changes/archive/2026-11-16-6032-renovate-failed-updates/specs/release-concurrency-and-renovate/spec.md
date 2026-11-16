## ADDED Requirements

### Requirement: Renovate pins no digest of a version input of an action
The shared preset SHALL pin the digests of github-actions and dockerfile dependencies, but not of a `uses-with` dependency of github-actions, such as the `version` input of trivy-action or setup-uv, because that input names a release tag and has no place for a digest.

#### Scenario: The digest pin rules are applied to each dependency type
- **WHEN** a test applies the pin rules of `.github/renovate/base.json` in order to the github-actions types `action`, `docker`, `container`, `service` and `uses-with`, and to the dockerfile types `final` and `stage`
- **THEN** only the github-actions type `uses-with` pins no digest

### Requirement: A security fix branch holds one update of each dependency
The shared preset SHALL set `vulnerabilityAlerts.separateMajorMinor` to false, so that the branch of a security fix holds only the newest fixed release of its dependency and never a minor and a major update of it together.

#### Scenario: The security settings are read
- **WHEN** a test reads `vulnerabilityAlerts` of `.github/renovate/base.json`
- **THEN** `vulnerabilityFixStrategy` is `highest` and `separateMajorMinor` is false

### Requirement: Renovate holds a security fix that the semgrep pins block
`.github/renovate.json` SHALL turn off the security fix of the indirect `mcp` and `opentelemetry-api` of `src/devops_cli/tools_lock/semgrep.in` only while the locked version is below the fix, because semgrep pins the vulnerable versions. The Dependency Dashboard footer SHALL name each held package and #3988.

#### Scenario: The holds are read against the semgrep lock
- **WHEN** a test reads the package rules of type `indirect`, the footer and `semgrep.txt`
- **THEN** each hold matches `pip-compile`, `semgrep.in`, one package and a version below its fix, and sets `enabled` to false
- **AND** each held package is locked below its fix, and the footer and each hold name #3988
