## ADDED Requirements

### Requirement: The collector deletes the host name of devops-cli metrics before it adds the deltas
The metrics pipeline of the OpenTelemetry collector SHALL run a transform processor after memory_limiter and before deltatocumulative that deletes the resource attribute host.name where telemetry.sdk.name is the SDK name of the tracer, so that an old and a new devops-cli build of one workload send one stream.

#### Scenario: The rule runs before the deltas are added
- **WHEN** The test reads the metrics pipeline of `k8s/otel/values.yaml` and the metric Resource that the tracer exports.
- **THEN** The processors before deltatocumulative are memory_limiter and transform/metric_resource, and transform/metric_resource deletes host.name from the resource where telemetry.sdk.name equals the exported SDK name.

## MODIFIED Requirements

### Requirement: The metric Resource holds only stable attributes
The metric Resource SHALL hold only service.name, service.namespace, service.instance.id, os.type and the attributes under telemetry.sdk, and SHALL hold no host.name, also when OTEL_RESOURCE_ATTRIBUTES sets other keys.

#### Scenario: Two tracers with one instance send equal metric Resources
- **WHEN** Two tracers start with different platform.node() values, and OTEL_RESOURCE_ATTRIBUTES sets the same service.instance.id and the host.name and k8s.pod.name of each pod.
- **THEN** Their metric Resources are equal, and no key of a metric Resource lies outside the allowed set.

#### Scenario: A span still names its host
- **WHEN** A tracer with a host name starts a span and records a counter.
- **THEN** The span Resource holds host.name, and the metric Resource holds no host.name.

### Requirement: The metric Resource reads the configured instance
The metric Resource SHALL take service.instance.id from OTEL_RESOURCE_ATTRIBUTES when that variable sets it, and from the host name when it does not.

#### Scenario: A Job pod sets one instance for its workload
- **WHEN** A tracer starts with OTEL_RESOURCE_ATTRIBUTES set to service.instance.id=devops-cli-job.
- **THEN** The metric Resource holds service.instance.id=devops-cli-job.

#### Scenario: A workstation names its host as the instance
- **WHEN** A tracer starts with no OTEL_RESOURCE_ATTRIBUTES on a host with a known name.
- **THEN** The metric Resource equals service.name, service.instance.id with the host name, os.type, telemetry.sdk.name and telemetry.sdk.language, and holds no host.name.

### Requirement: Two metric streams in one Prometheus series fire an alert
The Prometheus server SHALL fire DevopsCliMetricStreamsShareSeries with the severity warning when two target_info series of one job and instance stay for 30 minutes in a 15 minute lookback. The description SHALL tell the reader to compare the labels of the two series, and SHALL name a different telemetry_sdk_* label, another different label, a host_name label and the 15 minutes after which the alert clears.

#### Scenario: Two streams share a job and instance
- **WHEN** promtool evaluates two target_info series with the same job and instance.
- **THEN** The alert does not fire at 29 minutes, and fires at 30 minutes with the job and instance labels, the warning severity, the summary and the description.

#### Scenario: Two sparse writers share a job and instance
- **WHEN** promtool evaluates two target_info series of one job and instance that each get one sample in 15 minutes, at different minutes.
- **THEN** The alert fires at 40 minutes.

### Requirement: One stream and a short overlap stay quiet
The DevopsCliMetricStreamsShareSeries alert SHALL stay quiet for one target_info series, for a pod change in which two series overlap for 10 minutes, and for two series of a job outside devops-cli.* and roadmap-service.

#### Scenario: One series or a short overlap
- **WHEN** promtool evaluates one target_info series, or two target_info series of one job and instance that overlap for 10 minutes.
- **THEN** The alert does not fire, also at 34 minutes, the last minute at which the lookback holds the old series.

#### Scenario: A job outside the matcher
- **WHEN** promtool evaluates two target_info series of one instance of the job llm-gateway for 40 minutes.
- **THEN** The alert does not fire.

### Requirement: The rule set, the case file and the runbook list the alert
The alert rule set SHALL list DevopsCliMetricStreamsShareSeries in its own group, the promtool case file SHALL test it, and the runbook table SHALL give its row with the action in a cell that GFM renders. Each row of the Alerting table of `k8s/README.md` SHALL have no more cells than its header.

#### Scenario: The baseline and the case file list the alert
- **WHEN** The alert tests read the rule set, the promtool case file and the runbook table.
- **THEN** The baseline lists the alert with the warning severity, the case file names it, and the runbook has a row for it.

#### Scenario: The rendered runbook row holds the action
- **WHEN** The test parses the Alerting table with markdown-it-py.
- **THEN** Each row renders all cells of its source line, and the rendered cells of the alert row name target_info, the job, the instance, the label comparison, 30m and warning.
