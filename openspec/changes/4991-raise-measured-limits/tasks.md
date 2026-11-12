# Tasks

## 1. Hold the measured limits in the tests

Kind: other

Reads: `tests/commands/k8s/test_k8s.py`, `tests/ai/benchmark/test_k8s_llm_gateway.py`, `tests/server/routes/test_k8s_roadmap_service.py`. Changes: `tests/commands/k8s/test_k8s.py`, `tests/ai/benchmark/test_k8s_llm_gateway.py`, `tests/server/routes/test_k8s_roadmap_service.py`.

- [x] 1.1 In `test_k8s_workload_resource_limits_and_probes`, hold the CPU limit `500m` of the three Valkey exporters and node-exporter, the memory limits `1536Mi` (`alloy-metrics`) and `768Mi` (`alloy-logs`), and the Grafana resources (request `100m` and `512Mi`, limit `500m` and `2Gi`). Hold the gateway memory limit `4Gi` and the Service CPU limit `2`. See the three tests fail on the base
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`

## 2. Raise the limits in the manifests

Kind: other

Reads: `k8s/monitoring/grafana-values.yaml`, `k8s/llm/gateway/deployment.yaml`, `k8s/monitoring/k8s-monitoring-values.yaml`, `k8s/llm/valkey.yaml`, `k8s/llm/valkey-devops.yaml`, `k8s/argocd/values.yaml`, `k8s/devops/roadmap-service/deployment.yaml`. Changes: the same files.

- [x] 2.1 Set the values of the table of #4991, and write above each changed `resources` block a comment with the measured value and #4991. In the gateway comment, say not to set `MAX_REQUESTS_BEFORE_RESTART`
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s.py tests/ai/benchmark/test_k8s_llm_gateway.py tests/server/routes/test_k8s_roadmap_service.py`
- [x] 2.2 Check the rendered manifests and the change
  - Verification: `$ uv run devops ci --check --only k8s,openspec`

## Workflow follow-up

- Pending a person: 7 d after the merge, read the peak working set against the new limit and the throttled share of each container, and record them in a comment on the pull request.
- #4992 sizes every container with KRR, and #4993 adds the workload alerts. Both come after this item.
