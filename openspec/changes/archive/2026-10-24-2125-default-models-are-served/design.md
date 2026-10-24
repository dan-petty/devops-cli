# Design

## Context

`src/devops_cli/config/defaults.py` holds `DEFAULT_AI_MODEL` and `DEFAULT_BUNDLE_MODELS`. `src/devops_cli/ai/benchmark/runner.py` holds the task benchmark. `src/devops_cli/k8s/gpu_matrix.json` holds the hardware profiles and the Service aliases that `devops k8s gpu-matrix` shows. `tests/test_k8s_llm_gateway.py` holds the parser of `k8s/llm/gateway/config.yaml` and the served-model checks of #1969 and #2047. See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**

- Each default model of the CLI and each virtual model of the GPU matrix is a model or group that the gateway serves, and a test keeps it so.

**Non-Goals:**

- The `model_id` of a hardware profile and the `default_model` of a Service alias. They recommend a model that fits a GPU size, and most of those sizes have no tier in the homelab.
- `DEFAULT_EMBEDDING_BENCHMARK_MODELS`. An embedding benchmark compares candidate models, and #2125 does not name it.
- The model names in examples of help text and documents.

## Decisions

- **The default model is `qwen3.8:27b`.** The gateway config sends it to the tier of the default Ollama Service, and it is a group with deployments on each interactive tier and on the background tier. It is the model of the `devops-chat` route and of `config.example.yaml`, which moved to it in v0.2.5. Rejected: `gemma4:31b`, the model next to the old `gemma4:26b`. It also passes both checks, but its group has deployments on two tiers only, and no route or example names it.
- **"Served" for a default model is both checks.** The default provider calls Ollama, and `devops k8s configure-urls` points it at the default Ollama Service. So the check of #1969 on that Service applies, as for the fallback model of #2047. `provider: gateway` asks the gateway for the same name, so the group check of #2047 also applies. Rejected: the tier check alone. A model on the tier that is no group passes it, and `provider: gateway` would not find it.
- **The bundle holds the models that the defaults call.** `DEFAULT_BUNDLE_MODELS` is `DEFAULT_AI_MODEL` and `DEFAULT_RAG_EMBEDDING_MODEL`, so an air-gapped devcontainer holds the chat model and the embedding model of the defaults, and each has one source. Rejected: keep the small models with a comment that they are outside the gateway. The bundle then holds no model that a default calls, so the comment would give no valid reason.
- **The benchmark default is the configured model.** `BenchmarkRunner` runs `[settings.ai.model]` when it gets no candidate, as `devops ai benchmark` already passes. Rejected: a third model constant. It would be a second default for the same question.
- **A 70B profile names the group `deepseek-r1:70b`.** It is the group through which the gateway serves the 70B model of those profiles. Rejected: `devops-reasoning`. Its deployment calls `qwen3-coder:30b`, so a person who reads the matrix would ask for a 70B model and get a 30B model. Rejected: a new `devops-flagship` group in the gateway config. No code asks for it, and the change would add a route only to make a name valid.
- **The Service aliases change with the profiles.** The `virtual_model` of an alias is the same name in the same file, and `devops k8s gpu-matrix --aliases` shows it in the same Virtual Model column. The test reads both.
- **The defaults stay in the source, and a test binds them to the config.** The CLI cannot read the config at run time (#1969).

## Risks / Trade-offs

- [A user who set no `ai.model` used `gemma4:26b` on a local Ollama] → The CLI now asks for `qwen3.8:27b`. The user pulls it, or sets `ai.model`. The tool is alpha software, and `config.example.yaml` already named `qwen3.8:27b`.
- [A model leaves the default tier or the gateway] → The default-model check fails on the next pull request that changes the config or a default, and the author moves the default.
