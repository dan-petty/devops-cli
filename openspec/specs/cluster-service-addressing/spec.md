# cluster-service-addressing Specification

## Purpose
Which `k8s://` service addresses `devops k8s configure-urls --addressing proxy` writes: only the addresses that the Kubernetes API server reaches through its service proxy, with a warning that names the other modes for each other Service.

## Requirements

### Requirement: Proxy addressing writes only the addresses that the API server reaches
`devops k8s configure-urls --addressing proxy` SHALL send one GET of the Service root through the API server's service proxy for each Service that it finds, with no redirect. When the API server answers 503 with a `Status` of reason `ServiceUnavailable`, the command SHALL not write that key, and SHALL print a warning that names the key, the address, `--addressing fqdn` and `devops k8s port-forward`. Any other answer SHALL count as reached.

#### Scenario: The API server cannot dial the Service
- **WHEN** `configure-urls --addressing proxy --stack infra` runs and the API server answers the proxied GET of Grafana, the Prometheus server, Pyroscope and Tempo with its `ServiceUnavailable` Status
- **THEN** the command exits 0, writes `argocd.url` as `k8s://argocd/argocd-server:80`, leaves `grafana.url`, `prometheus.url`, `pyroscope.url` and `tempo.url` as they were, and prints a warning for each of the four keys that names `--addressing fqdn`

#### Scenario: The Service answers
- **WHEN** the proxied GET of a Service root gets a redirect, or a 503 that is not the API server's `Status`
- **THEN** the address counts as reached
