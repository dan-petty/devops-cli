# Task: Integrate Grafana Pyroscope to Monitoring Stack (#943)

**Issue**: [#943](https://github.com/dan-petty/devops-cli/issues/943)
**Status**: Done
**Milestone**: v0.2.25
**Priority**: priority/p2-medium
**Scope**: scope/k8s, scope/telemetry

## Description
The workstation and cluster monitoring stack provided metrics (Prometheus), logs (Loki), and distributed traces (Jaeger via OpenTelemetry Collector), but lacked continuous application and infrastructure profiling (flamegraphs, CPU execution time, memory allocation, and goroutine leak inspection) to diagnose performance bottlenecks and latency spikes at runtime:

- **Missing Profiling Tier**: Workloads could not be continuously profiled without manually attaching debuggers or profilers.
- **Unified Observability Integration**: Grafana lacked a native Pyroscope datasource to correlate trace spans and metric spikes directly with continuous profiling flamegraphs.
- **Zero-Trust Network Perimeter & Telemetry Opt-Out**: Network policies needed to allow profile scraping and ingestion on port 4040 while maintaining zero-trust network boundaries and disabling third-party phone-home telemetry.

## Key Changes
1. **Pyroscope Helm Chart & Values (`k8s/monitoring/pyroscope-values.yaml`)**:
   - Integrated `grafana/pyroscope` (v2.3.1) into the `infra` stack in `src/devops_cli/commands/k8s/stack_lifecycle.py`.
   - Configured single-binary deployment mode with `5Gi` `local-path` persistence for storage.
   - Deployed the bundled `alloy` child collector with automatic Kubernetes pod profile discovery based on `profiles.grafana.com/*` annotations.
   - Disabled non-functional telemetry/reporting via `alloy.alloy.enableReporting: false` (`--disable-reporting`).
2. **Grafana Continuous Profiling Datasource (`k8s/monitoring/grafana-values.yaml`)**:
   - Provisioned `grafana-pyroscope-datasource` pointing to `http://pyroscope.monitoring.svc.cluster.local:4040` (`uid: pyroscope`).
   - Verified active datasource health check (`{"message":"Data source is working","status":"OK"}`).
3. **NetworkPolicy Alignment (`k8s/monitoring/networkpolicy.yaml` & `k8s/otel/networkpolicy.yaml`)**:
   - Allowed ingress port 4040 for external, Traefik, and cross-namespace profiling push/query traffic.
   - Allowed egress port 4040 from the `otel` namespace for OpenTelemetry collector profile shipping.
4. **Testing & Documentation**:
   - Added `test_pyroscope_helm_release_and_grafana_datasource` to `tests/test_k8s.py` verifying chart release, namespace, repo, port 4040, and Grafana datasource provisioning.
   - Updated `test_monitoring_networkpolicy_specifics` in `tests/test_k8s_network_policies.py`.
   - Documented Pyroscope in `k8s/README.md`.

## Acceptance Criteria
- [x] `grafana/pyroscope` Helm chart added to `infra` stack in `_HELM_RELEASES_BY_STACK["infra"]`.
- [x] `k8s/monitoring/pyroscope-values.yaml` created with single-binary architecture, local-path storage, resource limits, and telemetry disabled.
- [x] Pyroscope datasource configured in `k8s/monitoring/grafana-values.yaml` with passing health check.
- [x] Network policies updated to permit port 4040 ingress and egress.
- [x] Unit and integration tests in `tests/test_k8s.py` and `tests/test_k8s_network_policies.py` pass.
- [x] `uv run devops ci` quality gates pass with 100% success.
