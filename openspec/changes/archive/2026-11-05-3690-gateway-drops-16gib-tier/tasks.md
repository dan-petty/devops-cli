# Tasks

## 1. Consumers of the tier (behavior)

- [x] 1.1 Mark `ollama-16gib` as `no` in the GPU placement table, add the routes of the GPU matrix to the consumers of the check, add the tests of the tier and of the pool window, and move the negative control to `ollama-64gib`.
  Verification: `uv run devops ci test tests/ai/benchmark/test_k8s_llm_gateway.py`
- [x] 1.2 Delete the tier from `DEFAULT_GATEWAY_REVIEW_SLOTS`, and update the tests that read the slot sum.
  Verification: `uv run devops ci test tests/http/test_gateway_review_stall.py tests/ai/review/test_review_pipeline.py tests/review/test_review_group_analysis.py tests/ai/client/test_ai_client_network.py tests/ai/review/test_review_benchmark.py`

## 2. Manifests and data (manifests)

- [x] 2.1 Delete the three deployments on `ollama-16gib-fast` from the gateway config, delete the routes of the tier from `gpu_matrix.json`, set `OLLAMA_MAX_LOADED_MODELS` to 1 on the DaemonSet, and move the devcontainer to `ollama-48gib` with `qwen3.8:27b`.
  Verification: `uv run devops ci test tests/ai/test_k8s_gpu_matrix.py tests/commands/test_devcontainer.py tests/ai/test_ai_gateway_render.py tests/k8s/test_gpu_thresholds.py tests/invariants/test_k8s_manifests.py`
- [x] 2.2 Confirm that the render owns no changed line.
  Verification: `uv run devops ai gateway render`

## 3. Documents (documents)

- [x] 3.1 Update `k8s/README.md`, `k8s/llm/profiles/README.md`, `docs/SELF_IMPROVEMENT.md`, the profiles header and the Ollama knowledge base.
  Verification: `uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
