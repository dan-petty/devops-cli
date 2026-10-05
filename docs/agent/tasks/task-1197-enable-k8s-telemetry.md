# Task: Enable Telemetry for Roadmap-Service and Kubernetes Services (#1197)

**Issue**: [#1197](https://github.com/dan-petty/devops-cli/issues/1197)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p1-high
**Scope**: scope/k8s, scope/telemetry

## Description
Enable telemetry for `roadmap-service` and any Kubernetes workloads deployed to namespace `devops` moving forward. Previously, the `k8s/devops/networkpolicy.yaml` perimeter blocked egress to the OpenTelemetry collector (`http://otel-collector-opentelemetry-collector.otel.svc.cluster.local:4318`), and `k8s/devops/configmap.yaml` had telemetry explicitly disabled (`enabled: false`). Furthermore, `roadmap-service` was not instrumented with HTTP request tracing middleware or batch job execution tracing.

This deliverable:
1. **Configures In-Cluster Telemetry Export**: Configures `telemetry.enabled: true` and `telemetry.endpoint: http://otel-collector-opentelemetry-collector.otel.svc.cluster.local:4318` in `k8s/devops/configmap.yaml` so all workloads mounting the shared ConfigMap automatically inherit the collector endpoint.
2. **Opens Perimeter Egress to OTel Collector**: Adds an egress rule to `k8s/devops/networkpolicy.yaml` (`devops-default-perimeter`) permitting TCP ports 4318 (HTTP) and 4317 (gRPC) to namespace `otel`. Because `devops-default-perimeter` applies to all pods in namespace `devops` (`podSelector: {}`), all current and future services or batch jobs gain egress to the OpenTelemetry Collector.
3. **Instruments Roadmap Service**:
   - Sets environment variable `OTEL_SERVICE_NAME: roadmap-service` in `k8s/devops/roadmap-service/deployment.yaml`.
   - Instruments `create_service_app` with HTTP request tracing and timing middleware using `get_tracer()`, extracting parent context from incoming headers and attaching `X-Process-Time`, `X-DevOps-Version`, `X-Trace-ID`, and `traceparent` headers to responses. High-frequency health probes and metric scrapes (`/healthz`, `/readyz`, `/metrics`) are bypassed from trace span creation to prevent collector trace storage flooding.
   - Instruments `RepoWorker._execute_batch` with `tracer.span("service.job <repo>")` recording attributes for repository, triggers, trigger types, duration, result, and bounded exception details.
4. **Documents Perimeter Reachability**: Updates `k8s/README.md` to document that `k8s/devops/` cluster jobs and services reach DNS, the LLM gateway, the OpenTelemetry collector in namespace `otel`, and public HTTPS.
5. **Updates Architectural & Contract Tests**:
   - Updates `tests/test_k8s_devops_runtime.py` to assert telemetry configuration in ConfigMap and four egress rules in NetworkPolicy.
   - Updates `tests/test_k8s_roadmap_service.py` to assert `OTEL_SERVICE_NAME` and telemetry configuration.
   - Adds unit tests in `tests/test_server_service.py` for request tracing middleware (headers, probe skipping) and batch job span recording.

## Acceptance Criteria
- [x] `k8s/devops/configmap.yaml` enables telemetry targeting the in-cluster OpenTelemetry collector at `http://otel-collector-opentelemetry-collector.otel.svc.cluster.local:4318`.
- [x] `k8s/devops/networkpolicy.yaml` permits egress on TCP 4318 and 4317 to namespace `otel`.
- [x] `k8s/devops/roadmap-service/deployment.yaml` sets `OTEL_SERVICE_NAME: roadmap-service`.
- [x] `src/devops_cli/server/service.py` instruments HTTP requests and batch executions with OpenTelemetry spans and headers while bypassing `/healthz`, `/readyz`, `/metrics`.
- [x] `k8s/README.md` documents OTel collector egress in `k8s/devops/`.
- [x] Unit and contract tests pass with 100% verification across all modified files.
- [x] Changelog fragment `changelog.d/1197.md` is present.
- [x] `uv run devops ci` passes with 100% green status across all quality gates.
- Pending a person: Live cluster deployment verification with `kubectl apply` and span inspection in Jaeger UI.

## Deliverables
- [x] `k8s/devops/configmap.yaml`
- [x] `k8s/devops/networkpolicy.yaml`
- [x] `k8s/devops/roadmap-service/deployment.yaml`
- [x] `k8s/README.md`
- [x] `src/devops_cli/config/constants.py`
- [x] `src/devops_cli/server/service.py`
- [x] `tests/test_k8s_devops_runtime.py`
- [x] `tests/test_k8s_roadmap_service.py`
- [x] `tests/test_server_service.py`
- [x] `changelog.d/1197.md`
- [x] `docs/agent/tasks/task-1197-enable-k8s-telemetry.md`
