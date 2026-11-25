## ADDED Requirements

### Requirement: The scans of the Runner Image job run at the same time
The `Runner Image` job of `ci.yml` SHALL run each image scan as a background step and SHALL wait for all of them before it ends, so a failed gate scan fails the job. `.github/actions/image-scan` SHALL give each `category` its own Trivy cache directory.

#### Scenario: The scans overlap and pass
- **WHEN** a person reads the `Runner Image` job of a pull request that changes image content
- **THEN** the scans start before the earlier scans end, no log holds a cache lock error, and each category uploads its SARIF
