## ADDED Requirements

### Requirement: An upstream status gauge holds one series for each service and component
`emit_service_status_telemetry` SHALL send `devops_cli_upstream_service_status` with the label `service` only, and `devops_cli_upstream_component_status` with the labels `service` and `component` only. The value holds the indicator or the component status, so a new status replaces the value of the one series.

#### Scenario: The indicator of a service changes
- **WHEN** GitHub reports the indicator `major` and then `none`
- **THEN** the export holds one series of `devops_cli_upstream_service_status` with `service=github`, and its last value is 0

#### Scenario: The status of a component changes
- **WHEN** the GitHub component `Actions` goes from `major_outage` to `operational`
- **THEN** the export holds one series of `devops_cli_upstream_component_status` for `Actions`, and its last value is 0
