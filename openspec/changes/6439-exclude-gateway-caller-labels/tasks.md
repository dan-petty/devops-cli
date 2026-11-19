# Tasks

## 1. Exclude the caller labels at the gateway source

Kind: other. Reads: `docs/TESTING.md`. Changes: `k8s/llm/gateway/config.yaml`, `k8s/llm/gateway/servicemonitor.yaml`, `tests/gate/k8s_checks/llm_gateway.py`.

- [x] 1.1 In `k8s/llm/gateway/config.yaml`, set `prometheus_exclude_labels: ["client_ip", "user_agent"]` under `litellm_settings`, before `callbacks: ["prometheus", "otel"]`, with a comment that says why (#4545, #6439)
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 1.2 In `k8s/llm/gateway/servicemonitor.yaml`, remove the comment and the `metricRelabelings` block with its two `labeldrop` rules
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 1.3 In `tests/gate/k8s_checks/llm_gateway.py`, delete `check_the_gateway_endpoint_drops_the_caller_labels` and the constant `SERVICE_MONITOR`, and say in the comment of `DROPPED_LABELS` that the gateway excludes the labels at the source (#4545, #6439)
  - Verification: `$ ! git grep -n -e check_the_gateway_endpoint_drops_the_caller_labels -e SERVICE_MONITOR -- src/ tests/`

## Workflow follow-up

- Pending a person: after the merge and the Argo CD sync of Application `llm`, run the live checks of the scenarios "The gateway series carry no caller labels" and, 24 h later, "Prometheus refuses no gateway sample".
- The stored gateway history from 2026-11-15T23Z to the rollout stays wrong; a person decides whether to mark it (see #4624).
- The alert `AlloyRemoteWriteSamplesFailed` has no runbook; a person decides whether a new item owns it (see #1131).
