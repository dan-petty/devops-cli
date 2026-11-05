# Tasks

## 1. Tiers, render and gateway routes (behavior)

- [x] 1.1 Write the failing tests: the settings of the two tiers, the model set of the gateway deployments that call them, the template, the render of a chat tier, and the default embedding Service.
  Verification: `uv run devops ci test tests/ai/benchmark/test_k8s_llm_gateway.py tests/k8s/test_gpu_thresholds.py`
- [x] 1.2 Make the render write an embedding deployment only for an embedding-only tier, and add `DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL` for the `devops-embedding` route.
  Verification: `uv run devops ci test tests/k8s/test_gpu_thresholds.py tests/ai/mcp/test_ai_gateway.py`

## 2. Manifests and defaults (manifests)

- [x] 2.1 Set the four values on `ollama-48gib` and `ollama-64gib`, load one model in the 48 GiB template, delete the routes of the other models and of the embedding model from the gateway config, and run `uv run devops ai gateway render --apply`.
  Verification: `uv run devops ai gateway render`
- [x] 2.2 Replace `qwen3-coder:30b` by `qwen3.8:27b` in the defaults, the GPU matrix, the default gateway routes and the tests, and delete the rows of other models for the two tiers.
  Verification: `! git grep -n 'qwen3-coder' -- src tests k8s`
- [x] 2.3 Run the gateway, render and matrix tests.
  Verification: `uv run devops ci test tests/ai/benchmark tests/k8s tests/ai/test_ai_gateway_render.py tests/ai/test_k8s_gpu_matrix.py tests/ai/mcp`

## 3. Documents (documents)

- [x] 3.1 Update `k8s/README.md`, `k8s/llm/profiles/README.md`, the Ollama knowledge base and the profiles header, and regenerate the documentation with `devops docs generate --sync-readme`.
  Verification: `uv run devops ci docs`

## Workflow follow-up

- Pending a person: after the merge, Argo CD restarts the pods `ollama-48gib` and `ollama-64gib`. Confirm that `ollama ps` on each shows `qwen3.8:27b` with context 262144 after the first request (`kubectl -n llm exec ds/ollama-64gib -c ollama -- ollama ps`).
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
