## ADDED Requirements

### Requirement: A chart update has the prefix of a release
The repository configuration SHALL give each update of the `helm` datasource the prefix `fix(deps):`, because the update also changes the version of its release in `HELM_RELEASES_BY_STACK`, which is runtime code. Each coupled group that holds a chart of `HELM_RELEASES_BY_STACK` SHALL set the same prefix.

#### Scenario: A chart update
- **WHEN** Renovate opens a pull request that moves a chart, alone or in the group `dcgm-exporter`
- **THEN** its title has the prefix `fix(deps):`, and release-please adds a changelog line for it
