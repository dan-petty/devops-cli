# Proposal: #5732

## Why
Operators need end-to-end visibility of system communication paths, service dependencies, and autonomous brain decisions. The current monitoring dashboards show metrics per subsystem or per host, but no single dashboard gives an interactive graph of service connections, network flows, and decision telemetry. Closes #5732.

## What Changes
- Add a new dashboard `k8s/monitoring/dashboards/system-topology.json` (`System Topology & Service Map`).
- Include three top-level rows:
  1. `Network & Ingress Topology`: visualizes ingress traffic flows by entrypoint and router-to-service routing.
  2. `Distributed Trace Service Map`: visualizes service dependencies with a Grafana `nodeGraph` panel powered by Tempo service map traces.
  3. `Project Brain & Decision Flow`: visualizes decision point activity by resolver, RAG retrieval latency, and embedding cache performance.
- Add `grafana-topology-dashboards` ConfigMap generator in `k8s/monitoring/dashboards/kustomization.yaml`.
- Update `PROVISIONED` and add unit tests in `tests/prometheus/test_k8s_monitoring_dashboards.py`.

## Capabilities
- `system-topology-dashboard`: Provide a dedicated system topology and service map dashboard in Grafana.

## Impact
Improves observability across microservices and autonomous agent pipelines without extra cluster load.

## Feasibility
The Tempo datasource is provisioned at `tempo` with service map support. Traefik and devops-cli Prometheus metrics are active. The dashboard static linter confirms panel validities.

## Existing Tool Considered
Grafana native Node Graph panel and Tempo service map query type. Using existing Grafana capabilities requires no custom code or external plugins.
