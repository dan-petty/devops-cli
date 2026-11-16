## ADDED Requirements

### Requirement: The metrics row reads its interval from its settings
The row `metrics` SHALL be due by `roadmap.metrics.interval_minutes`, which a round SHALL read from the settings at its start. The default SHALL be 13 minutes. The variable `DEVOPS_CLI_ROADMAP_METRICS_INTERVAL_MINUTES` SHALL set it, and a value below 1 SHALL stop the settings from loading. The row counts no queue, so the section SHALL hold no backlog setting.

#### Scenario: The default interval
- **WHEN** A test loads the settings with no source that sets `roadmap.metrics`.
- **THEN** `roadmap.metrics.interval_minutes` is 13, and `interval_minutes` is the only field of the section.

#### Scenario: A variable slows the metrics row
- **WHEN** A test sets `DEVOPS_CLI_ROADMAP_METRICS_INTERVAL_MINUTES` to 26 and runs a dry round 26 minutes and 25 minutes after the last success of metrics.
- **THEN** The round at 26 minutes lists metrics, and the round at 25 minutes does not.
