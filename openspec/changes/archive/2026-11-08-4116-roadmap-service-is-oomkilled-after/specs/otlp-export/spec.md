## ADDED Requirements

### Requirement: The export queue is bounded
The tracer SHALL keep at most `DEFAULT_OTEL_EXPORT_QUEUE_MAX_PAYLOADS` payloads that wait for export or are in export, and SHALL count each payload that it drops in `export_dropped`.

#### Scenario: A collector that does not answer
- **WHEN** the exporter blocks and the tracer sends 1000 payloads, with the cap at 16
- **THEN** the collector takes 16 payloads once it answers, and `export_dropped` is 984.
