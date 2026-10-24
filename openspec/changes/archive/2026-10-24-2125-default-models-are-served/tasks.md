# Tasks

## 1. The default models are served

- [x] 1.1 Write `test_every_default_model_is_a_model_that_the_default_ollama_tier_and_the_gateway_serve` in `tests/test_k8s_llm_gateway.py` with the checks of #1969 and #2047, and `test_a_benchmark_with_no_candidate_runs_the_configured_model` in `tests/test_ai_benchmark.py`, and verify that `uv run devops ci test tests/test_k8s_llm_gateway.py tests/test_ai_benchmark.py` fails on the base and names `gemma4:26b`, `qwen2.5-coder:7b` and `llama3.1:8b`
- [x] 1.2 Set `DEFAULT_AI_MODEL` to `qwen3.8:27b`, make `DEFAULT_BUNDLE_MODELS` the default chat and embedding models, make `BenchmarkRunner` run the configured `ai.model` when it gets no candidate, and verify that `uv run devops ci test tests/test_k8s_llm_gateway.py tests/test_ai_benchmark.py tests/test_model_bundle.py tests/test_ai_cmd.py` passes
- [x] 1.3 Regenerate the option default in the documents, and verify that `uv run devops docs generate --sync-readme` and `uv run devops docs check` pass

## 2. The GPU matrix names served groups

- [x] 2.1 Write `test_every_gpu_matrix_virtual_model_is_a_group_that_the_gateway_serves` in `tests/test_k8s_llm_gateway.py`, and verify that `uv run devops ci test tests/test_k8s_llm_gateway.py` fails on the base and names the eight profiles and five Service aliases with `devops-flagship`
- [x] 2.2 Replace each `devops-flagship` of `src/devops_cli/k8s/gpu_matrix.json` with `deepseek-r1:70b`, and verify that `uv run devops ci test tests/test_k8s_llm_gateway.py tests/test_k8s_gpu_matrix.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
