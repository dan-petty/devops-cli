## ADDED Requirements

### Requirement: The log row shows the warnings above all lines of the workload pods
The log row of a service dashboard SHALL hold "Logs: warnings and errors" (`h8`) above "Logs: all lines" (`h12`), on the `loki` data source. The query of all lines SHALL be `{namespace="<namespace>"} | pod=~"<workload>-[a-z0-9]+-[a-z0-9]+"`, and the warnings query SHALL add `| detected_level=~"(?i)(warn|warning|error|err|critical|fatal|panic)"`.

#### Scenario: The log row of a fixture build
- **WHEN** the test reads the panels of the row "Logs" of the build of the namespace `shop` and the workload `cart`
- **THEN** the two panels have these titles, queries and heights, in this order

### Requirement: The template build writes each dashboard next to its spec file
The `main` of `devops_cli.grafana.service_dashboard` SHALL write `<uid>.json` next to the spec file that it gets, for each spec of the file.

#### Scenario: A build into a folder
- **WHEN** `main` runs on a spec file with one spec in an empty folder
- **THEN** the folder holds the spec file and `<uid>.json`, which is the build of the spec

## REMOVED Requirements

### Requirement: Each committed service dashboard is the build of its spec
**Reason**: devops-cli holds no `services.toml` and no committed service dashboard, and the CI job builds none (#7290).
**Migration**: The environment repository builds its dashboards. See `The template build writes each dashboard next to its spec file`.
