# Proposal

## Why

Issue #2047: the default fallback model and the Open WebUI model list named `qwen2.5-coder:7b`, a model that no deployment of the gateway config names. `DEFAULT_AI_FALLBACK_MODEL` is the default of `devops ai failover` and `devops ai chaos-model`, and the harness model slots copied the same name. #1969 moved the gateway routes to models that the gateway serves, and left these places.

## What Changes

- `DEFAULT_AI_FALLBACK_MODEL` is `qwen3-coder:30b`, the model of the `devops-coder` route. The gateway config sends it to the tier of the default Ollama Service. `devops ai failover --target-model` and `devops ai chaos-model --fallback-model` show it as their default, and so do the MCP tools `ai_failover` and `ai_chaos_model`.
- The harness model slot takes its provider and model from `DEFAULT_AI_FALLBACK_PROVIDER` and `DEFAULT_AI_FALLBACK_MODEL`, and the sub-agent's model slot uses those defaults. The two `qwen2.5-coder:7b` literals are gone.
- `k8s/llm/values-open-webui.yaml` sets no `MODEL_FILTER_LIST`. Open WebUI removed that allow list in v0.4.0, so the list had no effect, and it named `qwen2.5-coder:7b` and `devops-flagship`, which the gateway does not serve. `DEFAULT_MODELS` is the one model setting of the values that Open WebUI reads, and it names `devops-chat`.
- A test fails when a place that names the default fallback model names a model that the gateway config does not send to a serving tier of the default Ollama Service. A test fails when `DEFAULT_MODELS` names a model that is no gateway group with a deployment on a serving tier, or when the values set `MODEL_FILTER_LIST` again.
- The option defaults and the Open WebUI manifest are observable, so the change carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-gateway-routing`: two requirements are added. The default fallback model is a model that the default Ollama tier serves, and each Open WebUI default model is a group that the gateway serves.

## Impact

- Code: `src/devops_cli/config/defaults.py` (`DEFAULT_AI_FALLBACK_MODEL`) and `src/devops_cli/ai/harness/slots.py` (`ModelSlot` and `SubAgentSlot` defaults).
- Manifest: `k8s/llm/values-open-webui.yaml`. Argo CD applies it after the merge.
- Tests: `tests/test_k8s_llm_gateway.py` and `tests/test_ai_chaos_model.py`.
- Documents: `docs/CLI_REFERENCE.md`, `docs/commands/ai.md` and `docs/MCP_TOOLS.md`, from `devops docs generate --sync-readme`.

## Feasibility

- On 2026-10-24 the live gateway Deployment mounted the ConfigMap `llm-gateway-config-<hash>` (`kubectl -n llm get deploy llm-gateway`, `kubectl -n llm get configmap`). Its `config.yaml` was equal to `k8s/llm/gateway/config.yaml`. Its model groups were `deepseek-r1:70b`, `devops-background`, `devops-chat`, `devops-coder`, `devops-reasoning`, `devops-review`, `gemma4:31b`, `gpt-oss:20b`, `qwen3-coder:30b`, `qwen3-embedding:0.6b` and `qwen3.8:27b`. No deployment named `qwen2.5-coder:7b`, and no group was `devops-flagship`.
- The live Open WebUI StatefulSet ran `ghcr.io/open-webui/open-webui:v0.11.4` with `DEFAULT_MODELS=devops-chat` and the `MODEL_FILTER_LIST` of the values, and with no `ENABLE_MODEL_FILTER` (`kubectl -n llm get statefulset open-webui`).
- Open WebUI source: `backend/open_webui/config.py` at v0.3.35 reads `MODEL_FILTER_LIST` only behind `ENABLE_MODEL_FILTER`, which defaults to false. At v0.4.0 `config.py` does not read it, at v0.11.4 `config.py`, `env.py` and `main.py` do not read it, and a GitHub code search of `open-webui/open-webui` for `MODEL_FILTER_LIST` finds 0 files (the same search for `RAG_EMBEDDING_MODEL` finds 7). The v0.4.0 changelog moves model access to group-based access control in Admin Settings. Thus the list had no effect, and the fix deletes it. It does not rename its models.
- At v0.11.4 `config.py` reads `DEFAULT_MODELS` with `os.getenv`, and `main.py` splits it at each comma.
- `devops ai failover` records the fallback in its flag, and `devops ai chaos-model` calls the fallback model through the `ollama` provider. The CLI cannot read the gateway config at run time: the wheel and the service image hold only `src/devops_cli`, as #1969 found. So the default stays in `defaults.py`, and a test binds it to the config with the check of #1969.
- On the base commit, `test_the_default_fallback_model_is_a_model_that_the_default_ollama_tier_serves` failed and named the three places with `qwen2.5-coder:7b`, and `test_every_open_webui_default_model_is_a_group_that_the_gateway_serves` failed on `MODEL_FILTER_LIST`.

## Existing Tool Considered

LiteLLM's `model_list` in `k8s/llm/gateway/config.yaml` is the record of the models that the gateway serves, and Open WebUI shows the models of its connections and keeps model access in its database. Nothing is built. The tests reuse the parser and the served-model check of #1969 in `tests/test_k8s_llm_gateway.py`. The change deletes `MODEL_FILTER_LIST` from the Open WebUI values and the two `qwen2.5-coder:7b` literals in `src/devops_cli/ai/harness/slots.py`.
