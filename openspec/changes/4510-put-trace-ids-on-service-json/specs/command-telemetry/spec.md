## MODIFIED Requirements

### Requirement: Loki datasource configures derived trace link to Tempo
The Grafana Loki datasource in `k8s/monitoring/grafana-values.yaml` SHALL configure two derived fields that target the Tempo datasource (`datasourceUid: tempo`): a regex field that finds the 32-character trace id after a `trace_id` key in a log line, also in the JSON form `"trace_id":"<id>"`, and a label field that matches the `trace_id` structured metadata of an OTLP log record.

#### Scenario: Derived field is configured in Loki datasource
- **WHEN** the Loki datasource configuration in `k8s/monitoring/grafana-values.yaml` is read
- **THEN** `jsonData.derivedFields` contains a regex entry targeting `datasourceUid` `tempo` whose `matcherRegex` finds the trace id in a Service JSON line
- **AND** it contains a label entry targeting `datasourceUid` `tempo` whose `matcherRegex` matches `trace_id`
