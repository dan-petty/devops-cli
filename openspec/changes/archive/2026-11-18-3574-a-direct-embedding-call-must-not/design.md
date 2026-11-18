# Design

## Decisions

- **Add the top-level setting `ai.embedding_ollama_urls`, defaulting to `[DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL]`.**: The chat URLs and the embedding URLs stay apart in the configuration file, and `devops k8s configure-urls` writes each one to its own Service. The default keeps the embedding Service of the gateway route.
- **Read only `ai.embedding_ollama_urls` in `_get_ollama_urls`, with no fallback to `ai.ollama_urls` or `ai.api_base_url`.**: A fallback would send an embedding request to the 48 GiB tier again whenever the setting is empty. The engine raises the existing `embedding_no_ollama_urls` error instead, which names the model and the provider.
- **Validate the setting with its own `get_embedding_ollama_urls` property.**: A bad entry then fails with a `ConfigurationError` that names `ai.embedding_ollama_urls`, and not the chat key.
- **Resolve the embedding Service in `_configure_llm_stack_urls`, beside the chat Service.**: The command already resolves a detected URL into a reachable address there. The embedding Service writes through the same helpers, so an unreachable cluster leaves the setting at its default.
- **Extend `tests/ai/benchmark/test_k8s_llm_gateway.py` with the tier guard.**: The file already holds `SINGLE_MODEL_TIERS`, `_tiers_of` and `_ollama_services`, so the guard reads the manifests with the readers that are there. One guard stays in one file.
- **Put the setting and resolver assertions in a new module `tests/ai/rag/test_rag_embedding_urls.py`.**: `tests/ai/rag/test_embedding_providers.py` builds engines over a web fake and asserts request bodies; the new assertions read a resolved URL list and a `ConfigurationError`, so they keep one concern per file.

## Rejected alternatives

- **Send every embedding call through the gateway alone.**: The gateway needs a URL, a key and a reachable port-forward, and the direct Ollama path serves a cluster without the gateway, as change 2524 kept it.
- **Keep `ai.ollama_urls` and add only the guard test.**: The guard would fail on the default configuration, because `src/devops_cli/commands/k8s/networking.py:501:DEFAULT_OLLAMA_CLUSTER_SERVICE, "llm", context=effective_context` writes the default Ollama Service, and the `ollama` provider would still reach the 48 GiB tier.
- **Default `ai.tasks.embedding.ollama_urls` and leave the resolver as it is.**: `_with_task` copies that value onto `ollama_urls` of the embedding task, and `_dispatch_embed` reads `self.ai_config.ollama_urls` to choose the provider. A non-empty default would send an embedding of any other provider to Ollama.
- **Add the setting and resolver assertions to `tests/ai/rag/test_embedding_providers.py`.**: That module builds an engine over a web fake and asserts the bodies of the requests; the new assertions read the resolved URL list and a `ConfigurationError`, so a module of their own keeps one concern per file.
