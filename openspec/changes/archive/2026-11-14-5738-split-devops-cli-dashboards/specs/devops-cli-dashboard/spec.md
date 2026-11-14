## MODIFIED Requirements

### Requirement: Each panel outside the Service rows has one unit and one axis
Each panel of `devops-cli.json` that is not a table SHALL have targets of one unit and no field override of `unit` or `custom.axisPlacement`. A panel with the unit `s` or `ms` SHALL hold no `histogram_count` target.

#### Scenario: A panel that breaks one rule
- **WHEN** the chart rule test reads a time series with a quantile target and a `histogram_count` target, or with an override that sets `custom.axisPlacement` to `right`
- **THEN** it reports one problem that names the rule

### Requirement: Each panel outside the Service rows names its signal and follows the step
Each panel of `devops-cli.json` SHALL have a description, a title in the form "Signal: measure", and no repeat. Only a stat SHALL fall back to `or vector(0)`. A time series target SHALL read only the windows `[$__interval]` and `[$__rate_interval]`, and SHALL NOT group by `command` or `sub_command`.

#### Scenario: The shipped dashboard is checked
- **WHEN** the chart rule test reads each panel of `devops-cli.json`
- **THEN** it reports no problem

#### Scenario: The hourly core bars of the Service
- **WHEN** promtool adds up the bars of "GitHub quota: core requests per hour" over 24 h on a fixture counter that starts with a zero sample and adds 30 requests each 15 min
- **THEN** the sum is within 1 % of the 2,880 requests of the counter in the range

## ADDED Requirements

### Requirement: The devops-cli dashboard provides navigation links to sibling dashboards
The dashboard `devops-cli.json` SHALL define top-level links pointing to `devops-roadmap-service-telemetry` and `devops-ai-rag` dashboards.

#### Scenario: Top-level links are read
- **WHEN** the dashboard `devops-cli.json` is loaded
- **THEN** its `links` list contains links to `/d/devops-roadmap-service-telemetry` and `/d/devops-ai-rag`
