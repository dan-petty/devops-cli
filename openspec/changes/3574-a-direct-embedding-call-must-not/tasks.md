# Tasks

## 1. Send a direct embedding request to the embedding URL

Reads: `src/devops_cli/config/settings.py`, `src/devops_cli/ai/rag/embeddings.py`, `src/devops_cli/config/defaults.py`, `tests/ai/rag/test_embedding_providers.py`. Changes: `src/devops_cli/config/settings.py`, `src/devops_cli/ai/rag/embeddings.py`, `tests/ai/rag/test_rag_embedding_urls.py` (new).

- [ ] 1.1 Add `tests/ai/rag/test_rag_embedding_urls.py`: assert that `AIConfig().get_embedding_ollama_urls == [DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL]`, that a set `ai.embedding_ollama_urls` replaces it, that a bad entry raises `ConfigurationError` with key `ai.embedding_ollama_urls`, and that `EmbeddingsEngine(AIConfig(provider="ollama", ollama_urls=[DEFAULT_OLLAMA_CLUSTER_URL]))._get_ollama_urls()` returns `[DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL]`. Run it and see it fail
  - Verification: `$ uv run devops ci test tests/ai/rag/test_rag_embedding_urls.py tests/ai/rag/test_embedding_providers.py` fails on the base
- [ ] 1.2 In `AIConfig` of `src/devops_cli/config/settings.py`, add `embedding_ollama_urls: Annotated[list[HttpUrlStr], Variable()] = Field(default_factory=lambda: [DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL], description=...)`, beside `ollama_urls`. Add the `get_embedding_ollama_urls` property that strips and validates each entry with the key `ai.embedding_ollama_urls`. In `_get_ollama_urls` of `src/devops_cli/ai/rag/embeddings.py`, return `self.ai_config.get_embedding_ollama_urls` and drop the `ai.ollama_urls` and `api_base_url` fallbacks. Import `DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL` in `settings.py`
  - Verification: `$ uv run devops ci test tests/ai/rag/test_rag_embedding_urls.py tests/ai/rag/test_embedding_providers.py` passes

## 2. Configure URLs writes the embedding Service

Reads: `src/devops_cli/commands/k8s/networking.py`, `tests/commands/k8s/test_k8s_networking.py`. Changes: `src/devops_cli/commands/k8s/networking.py`, `tests/commands/k8s/test_k8s_networking.py`.

- [ ] 2.1 In `tests/commands/k8s/test_k8s_networking.py`, add a test that patches `_detect_service_url` to answer for `ollama-fast` and for `ollama-24gib-embed-gpu0`, runs `devops k8s configure-urls --stack llm` with a settings double, and asserts that `ai.embedding_ollama_urls` holds the embedding Service URL and that `ai.ollama_urls` holds the default Ollama Service URL only. Run it and see it fail
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_networking.py tests/commands/k8s/test_k8s.py` fails on the base
- [ ] 2.2 Add `_update_embedding_ollama_urls(settings, configured, embedding_url)` beside `_update_ollama_urls`: it writes `settings.ai.embedding_ollama_urls = [embedding_url]` and `configured["ai.embedding_ollama_urls"] = embedding_url` when the URL is not None. In `_configure_llm_stack_urls`, detect `DEFAULT_OLLAMA_EMBEDDING_CLUSTER_SERVICE` in namespace `llm`, resolve it with `_resolve_accessible_url`, and pass it to the new function after `_update_ollama_urls`. Add `ai.embedding_ollama_urls` to `_NODEPORT_KEYS_LLM`
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_networking.py tests/commands/k8s/test_k8s.py` passes

## 3. Guard the default embedding URL against a one-model tier

Reads: `tests/ai/benchmark/test_k8s_llm_gateway.py`, `k8s/llm/profiles/services.yaml`, `k8s/llm/profiles/ollama-profiles.yaml`. Changes: `tests/ai/benchmark/test_k8s_llm_gateway.py`.

- [ ] 3.1 In `tests/ai/benchmark/test_k8s_llm_gateway.py`, add a `_single_model_tiers_of(url)` helper that returns `_tiers_of(url) & set(SINGLE_MODEL_TIERS)`. Add `test_the_default_embedding_url_names_no_tier_that_loads_one_chat_model`, which asserts `(bool(_tiers_of(DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL)), _single_model_tiers_of(DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL)) == (True, set())`. Add the negative control `test_the_embedding_url_check_names_the_48gib_tier`, which builds `http://ollama-48gib.llm.svc.cluster.local:11434` and asserts that `_single_model_tiers_of` returns `{"ollama-48gib"}`. Cite `#3574` and `#3567` in the docstrings
  - Verification: `$ uv run devops ci test tests/ai/benchmark/test_k8s_llm_gateway.py` passes

## 4. Regenerate the configuration documents

Reads: `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`. Changes: `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`.

- [ ] 4.1 Run `uv run devops docs generate --sync-readme` so `docs/CONFIGURATION.md` lists `ai.embedding_ollama_urls` with its default, beside `ai.ollama_urls`, `docs/ENV_VARS.md` lists its variable, and the task table reflects the new field
  - Verification: `$ uv run devops ci docs` passes
- [ ] 4.2 Edit `docs/CONFIGURATION.md` and `docs/ENV_VARS.md` by regenerating them, so the `ai` table lists `embedding_ollama_urls` with the embedding Service as its default, beside `ollama_urls`
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
