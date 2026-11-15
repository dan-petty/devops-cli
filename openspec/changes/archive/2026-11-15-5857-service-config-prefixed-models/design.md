# Design

## Decisions
- Update `configmap.example.yaml` to specify `openrouter/deepseek/deepseek-v4.1-flash-1017` for `ai.model`, tasks (`analysis`, `stage`, `implement`, `verification`, `chat`, `triage`), and the implement ladder (`edit`, `repair`).
- Update the embedding task in `configmap.example.yaml` to `local/qwen3-embedding:0.6b`.
- Update `values-open-webui.yaml` to configure `DEFAULT_MODELS: local/devops-chat` and `RAG_EMBEDDING_MODEL: local/qwen3-embedding:0.6b`.
- Update `grafana-values.yaml` to map `base` and `large` models to `local/qwen3.8:27b`.
- In test helpers, resolve model aliases using the gateway's `router_settings.model_group_alias` mapping when checking deployment coverage, context windows, and pricing groups.

## Rejected alternatives
- Keeping bare unprefixed names in cluster templates: Rejected because users requested full migration of service configuration to prefixed naming to align with gateway model aliases and clean spend attribution.
