# Tasks

## 1. The AI callers build their client at the entry point (refactor)

- [ ] 1.1 Move `ai/gateway.py`, `ai/pool_load.py`, `ai/library/docs_ingester.py`, `ai/providers/__init__.py`, `ai/models/ollama.py`, `ai/rag/embeddings.py` and `ai/spend/pricing.py` from `new_http_client` and `new_async_http_client` to `http_client` and `async_http_client`.
  Verification: `! git grep -nE "new_http_client|new_async_http_client|get_shared_client|get_shared_async_client" -- src/devops_cli/ai ':!src/devops_cli/ai/knowledge_base/devops_cli/libraries/httpx2.md'`
- [ ] 1.2 Check that each caller kept its timeouts, headers, event hooks and egress level.
  Verification: `uv run pytest tests/ai/test_ai_gateway_probes.py tests/ai/mcp/test_ai_gateway.py tests/ai/library/test_docs_ingester.py tests/ai/models/test_pydantic_ai_ollama.py tests/ai/test_pydantic_ai_profiles_and_providers.py tests/ai/rag/test_rag_embeddings.py tests/ai/spend/test_ai_spend_pricing.py tests/ai/test_llm_pool_metrics.py`

## 2. The tests of `tests/ai/` and `tests/review/` use the `web` and `dns` fixtures (test-only edits)

- [ ] 2.1 Add `serve_llm` to `tests/llm_stream_fakes.py`, and give `streamed` the `web` fake.
  Verification: `uv run pytest tests/ai/client/test_ai_streaming.py tests/ai/client/test_ai_client_network.py`
- [ ] 2.2 Move the tests of the model clients (`tests/ai/client/`, `tests/ai/test_*`, `tests/ai/spend/`, `tests/review/test_review_group_analysis.py`) from `route_client`, `route_llm_clients`, `route_retrying_client`, `public_dns` and `MockTransport` clients to `serve_llm` and `web`.
  Verification: `uv run pytest tests/ai/client tests/ai/spend tests/ai/review tests/review/test_review_group_analysis.py tests/ai/test_ai_model_sampling.py tests/ai/test_thinking_providers.py tests/ai/test_ai_client_style_request.py tests/ai/test_service_client_configured_urls.py`
- [ ] 2.3 Move the tests of the MCP tools, the gateway, the docs ingester, the RAG engine, the benchmark and the retries from `stub_web`, `scripted_resolver`, `record_connects` and the patches of `httpx2.Client` to `web` and `dns`.
  Verification: `uv run pytest tests/ai/mcp tests/ai/rag tests/ai/benchmark tests/ai/library tests/ai/retries tests/ai/models tests/ai/test_ai_gateway_portkey.py tests/ai/test_common_tools.py tests/ai/test_pydantic_ai_profiles_and_providers.py`
- [ ] 2.4 Check that no test of these two folders uses an old fake or patches an httpx2 class.
  Verification: `! git grep -nE "stub_web|StubWeb|public_dns|scripted_resolver|web_fakes|record_connects|ConnectRecorder|route_client|route_llm_clients|route_retrying_client|patch.object\(httpx2|setattr\(\"?httpx2\.Client|setattr\(httpx2\.Client" -- tests/ai tests/review`

## 3. Documents (documents)

- [ ] 3.1 Name `serve_llm` in `docs/TESTING.md`, and the entry point in the knowledge-base page of the Ollama provider.
  Verification: `uv run devops ci --check --only docs`
- [ ] 3.2 Check that the change folder is valid.
  Verification: `uv run devops openspec check`

## Workflow follow-up

- The next slices of #3758 move the callers outside `ai/`, and the tests that still use `route_client`, `route_llm_clients` and `route_retrying_client` (`tests/roadmap`, `tests/core`, `tests/http`). The last slice deletes the old factories, `stub_web`, `public_dns`, `ScriptedResolver`, `tests/web_fakes.py` and the three `route_*` helpers.
- The three batch-timeout tests of `tests/ai/rag/test_rag_embeddings.py` keep a fake socket under httpcore2's pool, which the `web` fake cannot give. A fake peer on a loopback socket in the http contract suite would let them move.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
