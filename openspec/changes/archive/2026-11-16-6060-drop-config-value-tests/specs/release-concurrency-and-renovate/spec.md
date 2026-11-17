## MODIFIED Requirements

### Requirement: A chart update has the prefix of a release
The repository configuration SHALL give each update of the `helm` datasource the prefix `fix(deps):`, because the update changes the chart that `deploy-stack` and Argo CD install: `deploy-stack` reads the version from the Application of the chart (#6060). Each coupled group that holds a chart SHALL set the same prefix.

#### Scenario: A chart update
- **WHEN** Renovate opens a pull request that moves a chart, alone or in the group `dcgm-exporter`
- **THEN** its title has the prefix `fix(deps):`, and release-please adds a changelog line for it
