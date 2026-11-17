# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests for the health route, the MCP server rollout and the gateway replica rule
  - Verification: `$ uv run devops ci test tests/ai/mcp/test_mcp_http.py tests/config/test_k8s_devops_runtime.py tests/ai/benchmark/test_k8s_llm_gateway.py`
- [x] 1.2 Add the health route, the rollout and the readiness probe
  - Verification: `$ uv run devops ci test tests/ai/mcp/test_mcp_http.py tests/config/test_k8s_devops_runtime.py tests/ai/benchmark/test_k8s_llm_gateway.py`

## 2. Documents

- [x] 2.1 Give the rollout, the health route and the reason for one gateway replica in `docs/CLUSTER.md`, `SECURITY.md` and `k8s/README.md`
  - Verification: `$ uv run devops ci docs`
