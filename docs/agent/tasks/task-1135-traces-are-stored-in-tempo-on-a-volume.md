# Task: Traces Are Stored in Tempo on a Volume, Linked to Logs and Profiles (#1135)

**Issue**: [#1135](https://github.com/dan-petty/devops-cli/issues/1135)
**Status**: Done
**Feasibility**: Verified against `grafana-community/tempo` `3.1.0` Helm chart (`helm template` and `helm show values`), `grafana/k8s-monitoring` `4.0.1` `integrations.tempo` values, and a live `docker.io/grafana/tempo:3.1.0` container (`POST /v1/traces` and `GET /api/v2/traces/{trace_id}` JSON fixture capture).

## Overview

Replaced the ephemeral in-memory `jaegertracing/all-in-one` deployment in the `otel` namespace with single-binary Grafana Tempo (`grafana-community/tempo` `3.1.0`) backed by a `10Gi` `local-path` PersistentVolumeClaim (`argocd.argoproj.io/sync-options: Prune=false,Delete=false`) with 7-day (`168h`) trace retention. Wired the OpenTelemetry Collector, Grafana `Tempo` datasource (`uid: tempo` with `tracesToLogsV2`, `tracesToProfiles`, and `lokiSearch`), Alloy `integrations.tempo` metrics scrape, network policies, Traefik ingress, and `devops-cli` (`telemetry`, `sandbox`, `k8s`, MCP, and built-in AI tools) to Tempo.

## Deliverables

- [x] Removed `k8s/otel/jaeger.yaml` and added `k8s/otel/tempo-values.yaml` plus `k8s/argocd/apps/tempo.yaml` (`grafana-community/tempo` `3.1.0`, `10Gi` `local-path` PVC with `Prune=false,Delete=false`, `168h` retention, `reportingEnabled: false`, OTLP gRPC `4317` and HTTP `4318` receivers only).
- [x] Pointed `k8s/otel/values.yaml` (`otlp_grpc/tempo` -> `tempo.otel.svc.cluster.local:4317`), `k8s/ingress/ingress-routes.yaml` (`tempo-ingress` -> `svc/tempo:3200`), and `k8s/otel/networkpolicy.yaml`, `k8s/monitoring/networkpolicy.yaml`, and `k8s/logging/networkpolicy.yaml` at Tempo (`app.kubernetes.io/name: tempo`).
- [x] Replaced the `Jaeger` Grafana datasource in `k8s/monitoring/grafana-values.yaml` with `Tempo` (`type: tempo`, `uid: tempo`, `url: http://tempo.otel.svc.cluster.local:3200`, `tracesToLogsV2` -> `loki`, `tracesToProfiles` -> `pyroscope`, `lokiSearch` -> `loki`) and enabled `integrations.tempo` in `k8s/monitoring/k8s-monitoring-values.yaml`.
- [x] Updated `k8s/monitoring/dashboards/otel-collector.json` to filter `exporter="otlp_grpc/tempo"` and provide a trace-search table panel backed by `"datasource": {"type": "tempo", "uid": "tempo"}`.
- [x] Replaced Jaeger trace querying with Tempo OTLP JSON trace querying (`GET /api/v2/traces/{trace_id}`) in `src/devops_cli/telemetry/waterfall.py` (`normalize_tempo_spans`, `query_tempo_trace`, `resolve_trace_spans`), `devops telemetry profile`, `devops telemetry status`, `devops telemetry open-ui`, and `devops sandbox traces`.
- [x] Replaced `JaegerConfig` (`settings.jaeger`) with `TempoConfig` (`settings.tempo`), `devops k8s jaeger` with `devops k8s tempo`, MCP `k8s_jaeger_info` with `k8s_tempo_info`, and built-in tool `k8s_jaeger_status` with `k8s_tempo_status`.
- [x] Captured real OTLP trace payload from `docker.io/grafana/tempo:3.1.0` (`GET /api/v2/traces/{trace_id}`) in `tests/fixtures/traces/tempo-otlp-trace.json` and added unit and manifest tests in `tests/test_k8s_tempo.py` and `tests/test_sandbox_traces.py`.
- Pending a person: Verify trace persistence across `kubectl rollout restart statefulset/tempo -n otel` and trace-to-logs/profiles navigation in Grafana Explore on a live cluster.
