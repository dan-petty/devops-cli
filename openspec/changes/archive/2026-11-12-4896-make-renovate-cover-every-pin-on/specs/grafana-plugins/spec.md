## MODIFIED Requirements

### Requirement: Each plugin update is its own pull request below the next major
The Renovate configuration SHALL give each Grafana plugin update the labels `type/chore`, `scope/deps` and `scope/infra`, allow only versions below the major after the pinned one, put each plugin in its own pull request, and add a pull request note that names `grafanaDependency` and links the record of the proposed release.

#### Scenario: The plugin rule
- **WHEN** a test reads the package rule that matches the plugin datasource, and the rule that labels the custom managers of `k8s/`
- **THEN** its `allowedVersions` is `<4.0.0` for pins of major 3, it sets no `groupName`, and a note names `grafanaDependency` and links `https://grafana.com/api/plugins/{{{depName}}}/versions/{{{newVersion}}}`
- **AND** the preset labels are `type/chore` and `scope/deps`, and the custom managers of `k8s/**` add `scope/infra`
