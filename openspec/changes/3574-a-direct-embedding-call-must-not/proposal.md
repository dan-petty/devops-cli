# Proposal

## Why

A direct Ollama embedding call reaches the 48 GiB tier through `ai.ollama_urls`, and Ollama unloads `qwen3.8:27b` to load the embedding model (#3574). The gateway route already sends embeddings to the embedding Service, so the direct path must do the same.

## What Changes

- Add the setting `ai.embedding_ollama_urls` to `src/devops_cli/config/settings.py`, defaulting to `[DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL]`, with a `get_embedding_ollama_urls` property that validates each entry.
- Resolve the embedding URLs in `src/devops_cli/ai/rag/embeddings.py` from `ai.embedding_ollama_urls` alone, so a direct embedding request never reads `ai.ollama_urls` or `ai.api_base_url`.
- Make `_configure_llm_stack_urls` in `src/devops_cli/commands/k8s/networking.py` write the embedding Service into `ai.embedding_ollama_urls` and keep the default Ollama Service in `ai.ollama_urls`, through a new `_update_embedding_ollama_urls` and the nodeport preview key.
- Add a guard to `tests/ai/benchmark/test_k8s_llm_gateway.py` that fails and names the tier when `DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL` selects a tier in `SINGLE_MODEL_TIERS`.
- Regenerate `docs/CONFIGURATION.md` and `docs/ENV_VARS.md`; the change carries a spec delta, so `skip_specs` is false.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `configured-service-urls`: Embedding URL setting, Embedding request reaches the embedding Service, Configure URLs writes the embedding Service
- `ai-gateway-routing`: Guard against a one-model tier

## Impact

- Code: `src/devops_cli/config/settings.py`, `src/devops_cli/ai/rag/embeddings.py`, `src/devops_cli/commands/k8s/networking.py`
- Documents: `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`
- Tests: `tests/ai/rag/test_rag_embedding_urls.py`, `tests/commands/k8s/test_k8s_networking.py`, `tests/ai/benchmark/test_k8s_llm_gateway.py`

## Feasibility

- The probes confirm the files that the issue cites, word for word: The path `src/devops_cli/ai/rag/embeddings.py` is a file of the staging commit. The path `src/devops_cli/config/defaults.py` is a file of the staging commit. The path `openspec/changes/archive/2026-11-05-3567-one-model-48-64gib-tiers/design.md` is a file of the staging commit.
- The same probe reports The path `ai.ollama_urls` is no file of the staging commit. That names a configuration key and not a file, so the issue cites a setting.
- `search_code` with `DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL` found `src/devops_cli/config/defaults.py:115:DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL: str = (` and `src/devops_cli/ai/gateway.py:78:"backend_url": DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL,`, so the embedding Service and its gateway route exist.
- `read_file` of `src/devops_cli/config/defaults.py` showed `src/devops_cli/config/defaults.py:106:DEFAULT_OLLAMA_CLUSTER_SERVICE: str = "ollama-fast"` and `src/devops_cli/config/defaults.py:114:DEFAULT_OLLAMA_EMBEDDING_CLUSTER_SERVICE: str = "ollama-24gib-embed-gpu0"`, so the default chat Service is not the embedding Service.
- `read_file` of `src/devops_cli/ai/rag/embeddings.py` showed `src/devops_cli/ai/rag/embeddings.py:715:or self.ai_config.ollama_urls`, so a direct embedding request reads the chat URLs today.
- The archived change 3567 records the cause: `openspec/changes/archive/2026-11-05-3567-one-model-48-64gib-tiers/design.md:10:The default Ollama Service is the 48 GiB tier.`
- `read_file` of `src/devops_cli/commands/k8s/networking.py` showed `src/devops_cli/commands/k8s/networking.py:501:DEFAULT_OLLAMA_CLUSTER_SERVICE, "llm", context=effective_context` and `src/devops_cli/commands/k8s/networking.py:606:_NODEPORT_KEYS_LLM: tuple[str, ...] = (`, so the command writes the chat Service today.
- `search_code` with `SINGLE_MODEL_TIERS` found `tests/ai/benchmark/test_k8s_llm_gateway.py:81:SINGLE_MODEL_TIERS = ("ollama-48gib", "ollama-64gib")` and the helper `tests/ai/benchmark/test_k8s_llm_gateway.py:def _tiers_of`, which maps a URL to the tiers that its Service selects.
- `search_code` with `def get_ollama_urls` found `src/devops_cli/config/settings.py:def get_ollama_urls`, the validator that the new embedding property follows. No symbol named `embedding_ollama_urls` exists, so the change creates it.
- `list_files` of `tests/ai/rag` showed that the module that the earlier draft read is not in the commit, so group 1 reads `tests/ai/rag/test_embedding_providers.py`, which exists and tests the Ollama embedding path, and the change creates `tests/ai/rag/test_rag_embedding_urls.py`.
- `EmbeddingsEngine._embed_ollama` needs a client of the Ollama embedding Service as a precondition, and its test doubles that client offline.
- `_detect_service_url` needs a client of the Kubernetes API as a precondition, and its test doubles the API.
- `_resolve_accessible_url` needs a network to probe the detected address as a precondition, and its test doubles the probe.
- First checks against the real system: `uv run devops ci test tests/ai/benchmark/test_k8s_llm_gateway.py`, which proves the tier guard against the committed manifests; `uv run devops k8s configure-urls --stack llm --dry-run`, which shows the two URLs that the command writes; `uv run devops ci docs`, which proves the generated documents list the new setting.

## Existing Tool Considered

Kubernetes NetworkPolicy and the LiteLLM gateway are the open, maintained tools for the admission rule and the gateway route, and they stay as they are. The need here is one configuration setting and one resolver change, which neither covers: the NetworkPolicy cannot see the model that a request names, and the gateway cannot stop a client that calls the Ollama Service directly. The change builds that small code itself and deletes no internal code.

## Dependencies

None.
