# Tasks

## 1. Quiet the errors and correct the comments

Reads: `k8s/llm/gateway/config.yaml`, `k8s/llm/gateway/deployment.yaml`.

Changes: `k8s/llm/gateway/config.yaml`, `k8s/llm/gateway/deployment.yaml`, `tests/k8s/test_llm_gateway_config.py`.

- [x] 1.1 Add the three config assertions and watch them fail.
  - Verification: `$ uv run devops ci test tests/k8s/test_llm_gateway_config.py`
- [x] 1.2 Set the switch, remove the dead keys, and correct the comments.
  - Verification: `$ uv run python -m tests.gate.k8s`

## Workflow follow-up

- Pending a person: merge after the grace-period fix, because the config edit rolls the gateway.
