# Design

## Context

`DEFAULT_AI_FALLBACK_MODEL` in `src/devops_cli/config/defaults.py` is the default of `devops ai failover` and `devops ai chaos-model`, and the harness builds its sub-agent's model slot from it. `k8s/llm/values-open-webui.yaml` sets the environment of Open WebUI. `tests/test_k8s_llm_gateway.py` holds the parser of `k8s/llm/gateway/config.yaml` and the served-model check of #1969. See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**

- The default fallback model and each Open WebUI default model is a model that the gateway serves, and a test keeps it so.

**Non-Goals:**

- The chaos fallback calls the Ollama URL of a new `AIConfig`, not a configured URL. Open item #1165 owns the service URLs.
- Other model defaults that are not the fallback model, such as the benchmark and bundle defaults.

## Decisions

- **The fallback model is `qwen3-coder:30b`.** It is the model of the `devops-coder` route, a coder model as `qwen2.5-coder:7b` was, and the gateway config sends it to the tier of the default Ollama Service and to ollama-64gib-standard. Rejected: `qwen3.8:27b`, the model of the `devops-chat` route. The tier also serves it, but the chaos prompt and the sub-agent work on code.
- **"Served" is the check of #1969 on the default Ollama Service.** The fallback provider is `ollama`, and a failover to direct Ollama calls the default Ollama Service (#1969). So the test asks the same question of the fallback model as of a route on that Service. The test module has one function for that question, and the route check and the fallback check both call it. Rejected: any model that a gateway deployment names. A model on another tier only would pass, and the default tier would not hold it.
- **An Open WebUI default model is served when it is a gateway group with a deployment on a serving tier.** Open WebUI asks the gateway, its OpenAI connection, for a model by its group name, as the RAG embedding test already checks for `RAG_EMBEDDING_MODEL`.
- **The values set no `MODEL_FILTER_LIST`.** Open WebUI v0.11.4 does not read it (proposal.md, Feasibility). Rejected: keep the list with served models only. The list would have no effect, and its comment said that it allowed models. Rejected: set `ENABLE_MODEL_FILTER`. v0.11.4 does not read it either. The gateway's model list is already the list of models that the OpenAI connection shows.
- **The default stays in the CLI, and a test binds it to the gateway config.** The CLI cannot read the config at run time (#1969).
- **The harness model slot takes the fallback constants.** The sub-agent's model slot then takes the model slot defaults, so the fallback model has one source.

## Risks / Trade-offs

- [A model leaves the default tier] → The fallback check fails on the next pull request that changes the config or the default, and the author moves the default.
- [A failover flag that `devops ai failover` wrote before this change names `qwen2.5-coder:7b`] → No running task reads the flag, and the next `devops ai failover` writes the new default.
