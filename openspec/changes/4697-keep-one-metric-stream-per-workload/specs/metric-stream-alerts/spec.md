## Purpose
The Prometheus alert that fires when two metric streams write one series, its promtool cases, the served-series check and the runbook row that names it.

## ADDED Requirements

### Requirement: Two streams in one series fire
The Prometheus server SHALL fire DevopsCliMetricStreamsShareSeries with the severity warning when two target_info series with the same job and instance stay for 30 minutes.

#### Scenario: Two streams share a job and instance
- **WHEN** promtool evaluates two target_info series with the same job and instance for 30 minutes.
- **THEN** The alert fires with the job and instance labels, the warning severity, a summary and a description.

### Requirement: One stream or a short overlap stays quiet
DevopsCliMetricStreamsShareSeries SHALL stay quiet for one target_info series and for a ten-minute overlap of two streams at a pod change.

#### Scenario: One series or a short overlap
- **WHEN** promtool evaluates one target_info series, or two target_info series with the same job and instance for 10 minutes.
- **THEN** The alert does not fire.

### Requirement: The alert selects only a served series
The alert expression SHALL select only a series that the stack serves, and the served-series check SHALL list target_info.

#### Scenario: The served-series check reads the expression
- **WHEN** The served-series check reads the expression of DevopsCliMetricStreamsShareSeries.
- **THEN** The expression names target_info and no other series.

### Requirement: The rule set and its promtool file list the alert
The alert rule set SHALL hold DevopsCliMetricStreamsShareSeries in its own group, and a promtool case file SHALL test it.

#### Scenario: The alert tests read the new group
- **WHEN** The alert tests read the rule set and the promtool cases.
- **THEN** The baseline rule list names the alert with the warning severity, and the promtool file tests it.

### Requirement: The runbook names the alert
The runbook SHALL list DevopsCliMetricStreamsShareSeries in its alert table with its job and instance labels, its 30-minute wait and its action.

#### Scenario: The runbook lists the alert
- **WHEN** A test reads the alert table of the runbook.
- **THEN** The table has a row for DevopsCliMetricStreamsShareSeries with what it means, its 30-minute wait, its warning severity and its action.
