# Task: Qdrant Metrics with an Authenticated Scrape, and Its Dashboard Row Restored (#823)

**Issue**: [#823](https://github.com/dan-petty/devops-cli/issues/823)
**Status**: Done
**Milestone**: v0.2.36
**Priority**: priority/p2-medium
**Scope**: scope/k8s
**Feasibility**: Verified against `docker.io/qdrant/qdrant:v1.19.1` container runtime (`/metrics` returns HTTP 401 without `Authorization: Bearer <key>` when `QDRANT__SERVICE__API_KEY` is set, and HTTP 200 with it), Qdrant `v1.19.1` source (`src/common/metrics.rs`), and cached Helm charts `qdrant/qdrant` 1.19.1 (`templates/servicemonitor.yaml`) and `grafana/k8s-monitoring` 4.5.2 (`alloy-metrics` ClusterRole rules).

## Description
Qdrant stayed unmonitored after #693 removed its row from `k8s/monitoring/dashboards/llm-stack.json` (whose queries used `or vector(0)` and referenced `app_http_requests_total`, which Qdrant never serves) and #734 deleted the static scrape job. With `QDRANT__SERVICE__API_KEY` set from Secret `qdrant-api-key`, Qdrant protects `/metrics` behind HTTP authentication (`401 Must provide an API key or an Authorization bearer token`), so pod-annotation scraping cannot scrape it without credentials.

This change restores Qdrant metrics scraping and its dashboard row:
- **Authenticated `ServiceMonitor` (`k8s/llm/values-qdrant.yaml`)**: Enables `metrics.serviceMonitor` on the `qdrant/qdrant` 1.19.1 Helm chart with `authorization` (`type: Bearer`, `credentials: {name: qdrant-api-key, key: api-key}`). Although Qdrant accepts either a read-only API key or the main API key on `GET /metrics`, `devops k8s push-secrets` (#741) provisions a single `llm/qdrant-api-key` Secret (`key: api-key`) and `values-qdrant.yaml` sets `readOnlyApiKey: false`, so the `ServiceMonitor` references `qdrant-api-key` directly without introducing a second unprovisioned Secret.
- **Alloy RBAC & NetworkPolicy verification**: In `k8s-monitoring` 4.5.2, `alloy-metrics` already holds a cluster-wide `ClusterRole` granting `get`, `list`, and `watch` on `secrets` across all namespaces, and `k8s/monitoring/networkpolicy.yaml` and `k8s/llm/networkpolicy.yaml` already allow TCP 6333 from `monitoring` to `llm`.
- **Qdrant `/metrics` capture (`tests/fixtures/metrics/qdrant.yaml`)**: Captures all 50 metric families and label sets from `docker.io/qdrant/qdrant:v1.19.1` configured with the chart's `production.yaml` settings (`cluster.enabled: true`, `telemetry_disabled: true`, `max_search_threads: 2`, and `QDRANT__SERVICE__API_KEY` set) after exercising collection creation, point upsert, and vector search.
- **Restored Qdrant row (`k8s/monitoring/dashboards/llm-stack.json`)**: Adds the `"Qdrant"` row (`id: 26`, `y: 68`) and `"qdrant"` dashboard tag with three panels over captured metric names and labels only, with no `or vector(...)` fallback:
  - **Qdrant Request Rate and Errors** (`id: 27`, unit `reqps`): `sum by (method, endpoint, status) (rate(rest_responses_total[5m]))` and non-2xx error rate `sum by (method, endpoint, status) (rate(rest_responses_total{status!~"2.."}[5m]))`.
  - **Qdrant Request Latency p95** (`id: 28`, unit `s`): `histogram_quantile(0.95, sum by (le, method, endpoint) (rate(rest_responses_duration_seconds_bucket[5m])))`.
  - **Qdrant Collections and Vectors** (`id: 29`, unit `short`): `sum(collections_total)`, `sum(collections_vector_total)`, and `sum by (collection) (collection_vectors)`.

## Acceptance Criteria
- [x] `k8s/llm/values-qdrant.yaml` enables `metrics.serviceMonitor` with `Bearer` authorization referencing Secret `qdrant-api-key` (`key: api-key`), and embeds no secret value in the repository.
- [x] `tests/fixtures/metrics/qdrant.yaml` records Qdrant `v1.19.1`'s metric families, types, and label names without label values.
- [x] `k8s/monitoring/dashboards/llm-stack.json` restores the Qdrant row (request rate and errors, request latency p95, collections and vectors) over captured metric names and labels only, with no `or vector(...)` fallback.
- [x] `tests/test_stack_dashboards.py`, `tests/test_k8s_qdrant_security.py`, and `tests/test_k8s.py` validate the Qdrant capture, the authenticated `ServiceMonitor`, the restored Qdrant panels, and the CRD installation ordering offline without network access.
- [x] `uv run devops grafana dashboards lint k8s/monitoring/dashboards` passes with 0 errors and 0 warnings.
- [x] `uv run devops ci` passes.
- Pending a person: on the homelab cluster, after `devops k8s deploy-stack` and `devops grafana dashboards sync`, `devops prometheus query 'up{namespace="llm", job=~".*qdrant.*"}'` (and `up{namespace="llm", service=~".*qdrant.*"}`) returns `1` and the Qdrant panels in `llm-stack.json` return data.

## Deliverables
- [x] `k8s/llm/values-qdrant.yaml`
- [x] `tests/fixtures/metrics/qdrant.yaml`
- [x] `k8s/monitoring/dashboards/llm-stack.json`, `k8s/monitoring/dashboards/prometheus-server.json`
- [x] `tests/test_stack_dashboards.py`, `tests/test_k8s_qdrant_security.py`, `tests/test_k8s.py`
- [x] `src/devops_cli/commands/k8s/stack_lifecycle.py`, `k8s/README.md`
- [x] `changelog.d/823.md`
