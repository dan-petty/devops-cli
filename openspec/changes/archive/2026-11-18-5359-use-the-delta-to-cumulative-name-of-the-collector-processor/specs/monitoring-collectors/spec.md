## MODIFIED Requirements

### Requirement: A stream with no delta for an hour starts again from zero
The `delta_to_cumulative` processor of the collector SHALL set `max_stale` to `1h`, because the roadmap-service rules read a series with no sample in the hour before as a new stream and count all of its last value.

#### Scenario: The collector values and the rules are read
- **WHEN** a test reads `k8s/otel/values.yaml` and `k8s/monitoring/prometheus-values.yaml`
- **THEN** `max_stale` of `delta_to_cumulative` is `1h`
- **AND** the rules hold a selector with `[1h] offset 1h`
