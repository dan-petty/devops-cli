# Tasks

## 1. The window of each deployment

- [x] Add failing tests: a window on each `ollama_chat` deployment equal to its tier, no `model_info` inside `litellm_params`, no `context_window_fallbacks`, and the pinned groups with the windows of `devops-review`
  - Verification: `uv run devops ci test tests/ai/benchmark/test_k8s_llm_gateway.py`
- [x] Move the four misplaced `model_info` blocks to the top level of their deployments, add the window to every other `ollama_chat` deployment, and remove `context_window_fallbacks`
  - Verification: `uv run devops ci test tests/ai/benchmark/test_k8s_llm_gateway.py tests/ai/test_ai_gateway_render.py` and `uv run devops ai gateway render`, which shows no difference
- [x] Update the comments of the config and the gateway text of `k8s/README.md` and `k8s/llm/profiles/README.md`, then regenerate the documents with `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci test tests/ai/benchmark/test_k8s_llm_gateway.py`

## 2. The close

- [ ] Run the fail-to-pass check and the full `uv run devops ci`
  - Verification: `uv run devops ci fail-to-pass --base origin/main` and `uv run devops ci`
