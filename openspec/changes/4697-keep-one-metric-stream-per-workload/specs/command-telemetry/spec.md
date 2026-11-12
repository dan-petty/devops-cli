## ADDED Requirements

### Requirement: The metric Resource holds only stable attributes
The metric Resource SHALL hold only service.name, service.namespace, service.instance.id, os.type and the attributes under telemetry.sdk, and SHALL hold no host.name.

#### Scenario: Two tracers with one instance send equal metric Resources
- **WHEN** Two tracers start with different platform.node() values and the same OTEL_RESOURCE_ATTRIBUTES service.instance.id.
- **THEN** Their metric Resources are equal, and no key of a metric Resource lies outside the allowed set.

#### Scenario: A span still names its host
- **WHEN** A tracer with a host name starts a span and records a counter.
- **THEN** The span Resource holds host.name, and the metric Resource holds no host.name.

### Requirement: The metric Resource reads the configured instance
The metric Resource SHALL take service.instance.id from OTEL_RESOURCE_ATTRIBUTES when that variable sets it.

#### Scenario: A Job pod sets one instance for its workload
- **WHEN** A tracer starts with OTEL_RESOURCE_ATTRIBUTES set to service.instance.id=devops-cli-job.
- **THEN** The metric Resource holds service.instance.id=devops-cli-job.

### Requirement: Both CronJob templates name one runner instance
Both CronJob templates SHALL set OTEL_RESOURCE_ATTRIBUTES to service.instance.id=devops-cli-job.

#### Scenario: Each CronJob container names the runner instance
- **WHEN** The runtime test reads the container environment of the two CronJob templates.
- **THEN** Each container sets OTEL_RESOURCE_ATTRIBUTES to service.instance.id=devops-cli-job.

### Requirement: Two metric streams in one Prometheus series fire an alert
The Prometheus server SHALL fire DevopsCliMetricStreamsShareSeries with the severity warning when two target_info series of one job and instance stay for 30 minutes.

#### Scenario: Two streams share a job and instance
- **WHEN** promtool evaluates two target_info series with the same job and instance for 30 minutes.
- **THEN** The alert fires once with the job and instance labels, the warning severity, and a summary and a description.

### Requirement: One stream and a short overlap stay quiet
The DevopsCliMetricStreamsShareSeries alert SHALL stay quiet for one target_info series and for a two-stream overlap of 10 minutes.

#### Scenario: One series or a short overlap
- **WHEN** promtool evaluates one target_info series, or two target_info series of one job and instance for 10 minutes.
- **THEN** The alert does not fire.

### Requirement: The alert selects only a served series
The alert expression SHALL select only a series that the stack serves, and the served-series list SHALL name target_info.

#### Scenario: The served-series check reads the new rule
- **WHEN** The alert tests check every expression against the served series.
- **THEN** The check reports no unserved series for DevopsCliMetricStreamsShareSeries.

### Requirement: The rule set, the case file and the runbook list the alert
The alert rule set SHALL list DevopsCliMetricStreamsShareSeries in its own group, the promtool case file SHALL test it, and the runbook table SHALL give its row.

#### Scenario: The baseline and the case file list the alert
- **WHEN** The alert tests read the rule set, the promtool case file and the runbook table.
- **THEN** The baseline lists the alert with the warning severity, the case file names it, and the runbook has a row for it.
