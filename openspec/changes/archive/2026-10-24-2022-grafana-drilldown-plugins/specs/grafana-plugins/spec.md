# Spec Delta

## Purpose

The plugins that the Grafana of the monitoring stack installs at start, and the version of each plugin that git holds.

## ADDED Requirements

### Requirement: Grafana pins each Drilldown app at its release for Grafana 13
The Grafana values SHALL pin each of the apps `grafana-lokiexplore-app`, `grafana-metricsdrilldown-app`, `grafana-pyroscope-app` and `grafana-exploretraces-app` at a final 3.x release, in the chart's `plugins` value, as `<id>@<version>`. Each 3.x release needs Grafana 13.1.0 or later.

#### Scenario: The four apps have a pin
- **WHEN** the Grafana values are read
- **THEN** the `plugins` value has an entry `<id>@<version>` for each of the four apps, and each version is a final release with the major number 3
