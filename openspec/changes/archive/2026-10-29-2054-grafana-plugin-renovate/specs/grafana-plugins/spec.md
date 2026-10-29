## ADDED Requirements

### Requirement: Renovate reads each Grafana plugin pin
The Renovate configuration SHALL have a regex custom manager that matches only `k8s/monitoring/grafana-values.yaml` and reads each `- <id>@<version>` entry of its `plugins` value, with a custom datasource whose `defaultRegistryUrlTemplate` is `https://grafana.com/api/plugins/{{packageName}}/versions` and `semver` versioning.

#### Scenario: The manager reads the four pins
- **WHEN** a test applies the manager's match strings to `k8s/monitoring/grafana-values.yaml`
- **THEN** the matches are the `plugins` entries, each with its plugin ID and version, and nothing else

#### Scenario: The datasource reads grafana.com
- **WHEN** a test reads the manager's `datasourceTemplate` and the custom datasource it names
- **THEN** the datasource reads `https://grafana.com/api/plugins/{{packageName}}/versions` as JSON with one JSONata transform of `items`

### Requirement: Each plugin update is its own pull request below the next major
The Renovate configuration SHALL give each Grafana plugin update the labels `type/chore` and `scope/infra`, allow only versions below the major after the pinned one, put each plugin in its own pull request, and add a pull request note that names `grafanaDependency` and links the record of the proposed release.

#### Scenario: The plugin rule
- **WHEN** a test reads the package rule that matches the plugin datasource
- **THEN** its `allowedVersions` is `<4.0.0` for pins of major 3, its labels are `type/chore` and `scope/infra`, it sets no `groupName`, and a note names `grafanaDependency` and links `https://grafana.com/api/plugins/{{{depName}}}/versions/{{{newVersion}}}`
