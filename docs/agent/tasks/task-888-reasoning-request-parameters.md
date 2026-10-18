# Task: Reasoning Request Parameters Follow Declared Capability (#888)

**Issue**: [#888](https://github.com/dan-petty/devops-cli/issues/888)
**Status**: Done
**Feasibility**: Verified against gateway `/model/info` schema, Ollama `/api/show` capabilities specification, and OpenAI/Copilot client parameter builders.

## Summary

Replaced model-name heuristics (`CONST_REASONING_MODEL_*` constants, name substring matching, and `:thinking` prefix checks) with capability-driven parameter selection:
- Gateway deployments declare `supports_reasoning: true` in `model_info` within `k8s/llm/gateway/configmap.yaml`, and the client queries `/model/info` cached per process. A model group (e.g. `devops-review`) receives reasoning parameters only if every deployment in the group declares support; mixed or undeclared deployments receive standard parameters.
- Models used directly without the gateway declare `supports_reasoning` in devops-cli model configuration (`AIConfig`, `AITaskOverride`). Undeclared models (including models named `o3`) receive standard parameters.
- Native Ollama client sends `think: true` only when thinking is enabled AND `supports_reasoning=True` is declared in config; when thinking is disabled or undeclared, no reasoning parameters (`think`, `reasoning_effort`) are sent. Transparent 400 error-text scraping and retries are eliminated.
- When `enable_thinking=False`, no reasoning parameters (`reasoning_effort`, `think`) are sent.
- Deleted `CONST_REASONING_MODEL_SUBSTRINGS`, `CONST_REASONING_MODEL_PREFIXES`, and `CONST_REASONING_MODEL_EXACT`.

## Deliverables

- [x] Declared `supports_reasoning: true` under `model_info` for `gpt-oss:20b` and `devops-review` (`gpt-oss:20b` deployment) in `k8s/llm/gateway/configmap.yaml`.
- [x] Added `DEFAULT_AI_SUPPORTS_REASONING` in `src/devops_cli/config/defaults.py`, `AI_SUPPORTS_REASONING` in `src/devops_cli/config/options.py`, and `supports_reasoning` field to `AIConfig` and `AITaskOverride` in `src/devops_cli/config/settings.py`.
- [x] Added cached `/model/info` capability resolution helper in `src/devops_cli/ai/gateway.py` enforcing that multi-deployment groups require unanimous `supports_reasoning: true`.
- [x] Updated `OpenAICompatProviderMixin._build_compat_payload` and `_apply_reasoning_params` in `src/devops_cli/ai/client/openai.py` to route parameters based on declared capability and send no reasoning parameters when thinking is disabled.
- [x] Updated native Ollama client in `src/devops_cli/ai/client/ollama.py` to send `think: true` only when enabled and `supports_reasoning=True` is declared, omitting reasoning parameters when undeclared or disabled, and removing 400 error text retry handlers.
- [x] Removed `CONST_REASONING_MODEL_SUBSTRINGS`, `CONST_REASONING_MODEL_PREFIXES`, and `CONST_REASONING_MODEL_EXACT` from `src/devops_cli/config/constants.py` and updated `src/devops_cli/ai/client/models.py`.
- [x] Added comprehensive unit tests covering fake `/model/info` payloads, unanimous vs mixed deployment groups, undeclared `o3` models, disabled thinking payloads, and Ollama `/api/show` capability probing.
