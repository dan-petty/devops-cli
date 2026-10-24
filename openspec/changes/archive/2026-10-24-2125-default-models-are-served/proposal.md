# Proposal

## Why

Issue #2125: four defaults of the CLI named models or groups that `k8s/llm/gateway/config.yaml` does not serve. #2047 bound `DEFAULT_AI_FALLBACK_MODEL` and the Open WebUI default model to the gateway config, and left these places:

- `DEFAULT_AI_MODEL`, the default of `ai.model`, was `gemma4:26b`. The gateway config names only `gemma4:31b`.
- `DEFAULT_BUNDLE_MODELS`, the models of `devops ai bundle-models`, was `qwen2.5-coder:7b` and `llama3.1:8b`.
- `BenchmarkRunner` ran `qwen2.5-coder:7b` when it got no candidate.
- The `virtual_gateway_model` of each 70B profile of `src/devops_cli/k8s/gpu_matrix.json`, and the `virtual_model` of each Service alias of 48 GiB and more, was `devops-flagship`. The gateway config has no such group.

## What Changes

- `DEFAULT_AI_MODEL` is `qwen3.8:27b`. The gateway config sends it to the tier of the default Ollama Service, and it is a gateway group with deployments on each interactive tier and on the background tier. It is the model of the `devops-chat` route and of `config.example.yaml`. `docs/CONFIGURATION.md` shows the new default.
- `DEFAULT_BUNDLE_MODELS` is `DEFAULT_AI_MODEL` and `DEFAULT_RAG_EMBEDDING_MODEL`: the models that the default chat and embedding tasks call. The two literals are gone.
- `BenchmarkRunner` with no candidate runs the configured `ai.model`, as `devops ai benchmark` does when `--models` names none. The `qwen2.5-coder:7b` literal is gone.
- In `gpu_matrix.json`, each `devops-flagship` is `deepseek-r1:70b`, the gateway group that serves the 70B model of those profiles. `devops k8s gpu-matrix` shows it in its Virtual Model column.
- A test fails when a default model of the CLI is not a model that the gateway config sends to the tier of the default Ollama Service, or is no gateway group with a deployment on a serving tier. A test fails when a virtual model of the GPU matrix is no gateway group with a deployment on a serving tier. Both use the served-model checks of #1969 and #2047.
- The option default and the output of `devops k8s gpu-matrix` are observable, so the change carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-gateway-routing`: two requirements are added. Each default model of the CLI is a model that the default Ollama tier and the gateway serve, and each virtual model of the GPU matrix is a group that the gateway serves.

## Impact

- Code: `src/devops_cli/config/defaults.py` (`DEFAULT_AI_MODEL`, `DEFAULT_BUNDLE_MODELS`), `src/devops_cli/ai/benchmark/runner.py` (`BenchmarkRunner`), `src/devops_cli/k8s/gpu_matrix.json` and `src/devops_cli/k8s/gpu_matrix.py` (a comment).
- Tests: `tests/test_k8s_llm_gateway.py`.
- Documents: `docs/CONFIGURATION.md`, from `devops docs generate --sync-readme`.
- A user who set no `ai.model` gets `qwen3.8:27b` in place of `gemma4:26b`.

## Feasibility

- On 2026-10-24 the live gateway Deployment mounted the ConfigMap `llm-gateway-config-<hash>`, and its `config.yaml` was equal to `k8s/llm/gateway/config.yaml` (`kubectl -n llm get deploy llm-gateway`, `kubectl -n llm get configmap`). Its groups were `deepseek-r1:70b`, `devops-background`, `devops-chat`, `devops-coder`, `devops-reasoning`, `devops-review`, `gemma4:31b`, `gpt-oss:20b`, `qwen3-coder:30b`, `qwen3-embedding:0.6b` and `qwen3.8:27b`. No deployment named `gemma4:26b`, `qwen2.5-coder:7b` or `llama3.1:8b`, and no group was `devops-flagship`.
- The readers of each name, from the source:
  - `AIConfig.model` takes `DEFAULT_AI_MODEL`. The default provider is `ollama`, and `devops k8s configure-urls` points `ai.ollama_urls` at the default Ollama Service or at a port-forward to it. With `provider: gateway`, the client asks the gateway for the model by its name. So the default must be on the tier of the default Ollama Service and be a gateway group.
  - `bundle_ollama_models` writes `DEFAULT_BUNDLE_MODELS` into the manifest of `devops ai bundle-models` for an air-gapped devcontainer. Neither old model was the default chat model or the default embedding model, so the bundle did not hold the models that the defaults call.
  - `devops ai benchmark` passes `[settings.ai.model]` when `--models` names none. `BenchmarkRunner` used its own literal only when it got an empty list, so the two defaults were different.
  - Only `devops k8s gpu-matrix` reads `virtual_gateway_model` and the alias `virtual_model`, to show them. No code routes with them.
- `git log -S` shows that `config.example.yaml` changed `model: gemma4:26b` to `model: qwen3.8:27b` in v0.2.5 and the default stayed. `devops-flagship` left the gateway config in v0.2.24, with the vLLM backend of `cogito-v2:70b`. Since then the gateway serves the 70B model `deepseek-r1:70b` as the group `deepseek-r1:70b`.
- On the base commit, `test_every_default_model_is_a_model_that_the_default_ollama_tier_and_the_gateway_serve` failed and named `gemma4:26b`, `qwen2.5-coder:7b` and `llama3.1:8b` at their three places, and `test_every_gpu_matrix_virtual_model_is_a_group_that_the_gateway_serves` failed and named the eight profiles and five Service aliases with `devops-flagship`.
- The CLI cannot read the gateway config at run time: the wheel and the service image hold only `src/devops_cli` (#1969). So the defaults stay in the source, and a test binds them to the config.

## Existing Tool Considered

LiteLLM's `model_list` in `k8s/llm/gateway/config.yaml` is the record of the models that the gateway serves. Nothing is built. The tests reuse the parser and the served-model checks of #1969 and #2047 in `tests/test_k8s_llm_gateway.py` (`_off_the_gateway`, `_groups_off_the_gateway`). The change deletes the `qwen2.5-coder:7b` and `llama3.1:8b` literals of `DEFAULT_BUNDLE_MODELS` and the `qwen2.5-coder:7b` literal of `BenchmarkRunner`.
