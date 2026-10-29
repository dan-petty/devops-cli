# Tasks

## 1. The documents describe the least-busy gateway

- [x] Rewrite the tune paragraph of `k8s/README.md`, and remove the weights from its `qwen3-coder:30b` and `gpt-oss:20b` item
  - Verification: `uv run devops docs check`
- [x] Remove the weights from the two `devops-review` comments of `k8s/llm/gateway/config.yaml`, and from the model comparison paragraph of `docs/SELF_IMPROVEMENT.md`
  - Verification: `uv run devops ci test tests/test_k8s_llm_gateway.py`

## 2. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 1971-gateway-tune-least-busy`

## Workflow follow-up

- #2592: `devops ai gateway tune` stops recommending weights and a concurrency that the gateway does not read.
- Pending a person: after Argo CD syncs the merge, check that the gateway pod rolled onto the new ConfigMap and is ready.
