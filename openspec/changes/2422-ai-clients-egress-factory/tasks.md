# Tasks

## 1. The level test has a row for each AI service caller

- [x] Add failing rows to `test_each_caller_dials_at_its_level` for each caller of the table, with and without `ai.allow_private_network`, and make the test fail when a caller host name reaches the dial; add `test_each_ai_service_caller_dials_the_address_it_checked`, where each host answers a public address and then cloud metadata
  - Verification: `uv run devops ci test tests/test_http_egress.py`

## 2. The gateway probes, the connect probe and the pool-load query

- [ ] Give the gateway model query, the gateway health probe and the backend probe a factory client at the configured level, and delete their `validate_url_egress` calls
  - Verification: `uv run devops ci test tests/test_http_egress.py tests/test_ai_gateway.py tests/test_ai_gateway_portkey.py`
- [ ] Give the `devops ai gateway connect` probe a private-level factory client, and delete its `validate_url_egress` call
  - Verification: `uv run devops ci test tests/test_http_egress.py tests/test_ai_gateway.py`
- [ ] Make `prometheus_query` take the level from its caller, give it the configured level from `devops ai gateway load`, and delete the `validate_url_egress` and `validate_service_url` calls
  - Verification: `uv run devops ci test tests/test_http_egress.py tests/test_llm_pool_metrics.py`

## 3. The embeddings engine

- [ ] Give the batch client, the Ollama batch and the two dimension probes factory clients at the configured level, and delete the four `validate_configured_service_url` calls
  - Verification: `uv run devops ci test tests/test_http_egress.py tests/test_rag_embeddings.py tests/test_rag_loopback_policy.py`

## 4. The pricing fetch and the documentation crawler

- [ ] Fetch a `--source` URL at the configured level and the default registry at the public level with factory clients, and delete the `UpdatePrices.fetch()` branch
  - Verification: `uv run devops ci test tests/test_http_egress.py tests/test_ai_spend_pricing.py`
- [ ] Crawl with a public-level factory client, and delete the two `validate_service_url` calls
  - Verification: `uv run devops ci test tests/test_http_egress.py tests/test_docs_ingester.py`

## 5. The pydantic-ai Ollama model and provider

- [ ] Give the Ollama provider a client from `new_async_http_client` at the configured level of the settings in use, and delete `_is_cloud_metadata_host`, the `validate_url` call and the `allow_private` parameters
  - Verification: `uv run devops ci test tests/test_http_egress.py tests/test_pydantic_ai_ollama.py`
- [ ] Delete the `validate_configured_service_url` call of `create_pydantic_ai_provider` and the `ConfigurationError` branch of the bridge for an address refusal
  - Verification: `uv run devops ci test tests/test_http_egress.py tests/test_pydantic_ai_profiles_and_providers.py`

## 6. The benchmark endpoints

- [ ] Delete the `validate_url` calls of the chat and embedding runners, and check `--servers` with `HttpUrlStr` inside the error block of the command
  - Verification: `uv run devops ci test tests/test_http_egress.py tests/test_ai_benchmark.py tests/test_embedding_benchmark.py`

## 7. Documentation

- [ ] Name the moved clients in `README.md`, `docs/KNOWN_ISSUES.md` and the pydantic-ai page of the knowledge base
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops ci test tests/test_docs_sync.py`

## 8. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 2422-ai-clients-egress-factory`

## Workflow follow-up

- Part 5 (#2437) removes the pre-flight check of `ai/client/*`, deletes `_resolve_host_ips` and `_enforce_non_private_ssrf`, and writes the general statement that every HTTP client is checked at the connect.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
