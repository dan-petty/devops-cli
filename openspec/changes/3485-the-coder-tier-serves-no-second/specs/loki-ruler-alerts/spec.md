## Purpose
The Loki ruler that evaluates alert rules over the log lines Loki stores and sends its alerts to Alertmanager.

## ADDED Requirements

### Requirement: The Loki ruler fires on Ollama tier evictions
The Loki ruler SHALL evaluate the rule `OllamaTierEvictions`, which counts the eviction lines of the stream `{service_name="ollama-48gib"}` over a window, and SHALL fire when the count is above the configured threshold.

#### Scenario: Eviction lines above the threshold fire the alert
- **WHEN** A fixture holds more eviction lines than the threshold of the rule in its window
- **THEN** The rule returns a firing alert named `OllamaTierEvictions` for the stream `ollama-48gib`

#### Scenario: No eviction line keeps the alert quiet
- **WHEN** A fixture holds no eviction line in the window of the rule
- **THEN** The rule returns no firing alert

#### Scenario: The ruler loads the rule and sends its alerts to Alertmanager
- **WHEN** The values of `k8s/logging/loki-values.yaml` set the ruler storage and its Alertmanager URL
- **THEN** The ruler reads the rule file of the mounted ConfigMap and sends its alerts to `prometheus-alertmanager.monitoring.svc.cluster.local:9093`

### Requirement: The Loki ruler reaches Alertmanager through the network policies
The network policies SHALL admit TCP 9093 from the `logging` namespace to the Alertmanager pod of the `monitoring` namespace, and SHALL admit no other port for that pair.

#### Scenario: The ruler reaches Alertmanager on 9093
- **WHEN** A pod of the `logging` namespace dials the Alertmanager pod of `monitoring` on TCP 9093
- **THEN** The egress rule of `k8s/logging/networkpolicy.yaml` and the ingress rule of `k8s/monitoring/networkpolicy.yaml` both admit the connection

#### Scenario: Another port of Alertmanager stays closed to logging
- **WHEN** A pod of the `logging` namespace dials the Alertmanager pod of `monitoring` on TCP 9094
- **THEN** No rule of either network policy admits the connection
