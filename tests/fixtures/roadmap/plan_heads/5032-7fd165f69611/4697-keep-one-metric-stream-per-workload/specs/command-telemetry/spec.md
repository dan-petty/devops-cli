## ADDED Requirements

### Requirement: The span resource keeps the host name
The span and log Resource SHALL keep host.name when the host has a name.

#### Scenario: A span names the host and a metric does not
- **WHEN** A tracer with a host name starts a span and records a counter.
- **THEN** The span Resource holds host.name, and the metric Resource holds no host.name.
