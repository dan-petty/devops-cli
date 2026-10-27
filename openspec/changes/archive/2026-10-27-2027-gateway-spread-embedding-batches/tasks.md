# Tasks

## 1. Gateway routing configuration

- [x] 1.1 Write failing test `test_embedding_group_spreads_batches_over_order_1_tiers` in `tests/test_k8s_llm_gateway.py` asserting that `router_settings.routing_groups` configures `simple-shuffle` for `qwen3-embedding:0.6b` (`uv run pytest tests/test_k8s_llm_gateway.py -k test_embedding_group_spreads_batches_over_order_1_tiers`)
- [x] 1.2 Add `routing_groups` under `router_settings` in `k8s/llm/gateway/config.yaml` to route `qwen3-embedding:0.6b` with `simple-shuffle` (`uv run pytest tests/test_k8s_llm_gateway.py`)
- [x] 1.3 Update comments in `k8s/llm/gateway/config.yaml` and description in `k8s/README.md` (`uv run devops docs generate --sync-readme`)

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
