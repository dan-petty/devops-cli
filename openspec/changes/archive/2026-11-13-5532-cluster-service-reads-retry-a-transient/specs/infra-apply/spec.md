## MODIFIED Requirements

### Requirement: The cluster is healthy before the apply
The command SHALL refuse the apply when a node of the kube context that is not the node of a host out of service is not Ready or has memory, disk or PID pressure, or when `prometheus.url` is set and a `severity="critical"` alert fires or the query gets no answer. A query that gets no answer after the attempts of `SERVICE_READ_RETRY` SHALL be a problem of the gate whose text holds the line of `ServiceRequestError`. The gate SHALL keep its own wait loop.

#### Scenario: A node with memory pressure
- **WHEN** node-2 has `MemoryPressure` before the apply
- **THEN** the command exits 1, names node-2 and `MemoryPressure`, and drains no node

#### Scenario: A critical alert
- **WHEN** `prometheus.url` is set and the alert `KubeNodeNotReady` with `severity="critical"` fires
- **THEN** the health gate names the alert

#### Scenario: Prometheus answers only after the uncordon
- **WHEN** Prometheus does not answer the first two queries of the alert wait after a host, each after all of its attempts, then answers with no alert
- **THEN** the wait ends with no problem

#### Scenario: Prometheus stays down
- **WHEN** Prometheus answers 503 to each attempt of the query of the critical alerts
- **THEN** the health gate has one problem that names Prometheus, `503` and `4 attempts`
