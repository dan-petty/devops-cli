# Tasks

## 1. The investigation and the Qdrant client tests run on edge fakes (test-only edits)

- [x] 1.1 Give `FakeEmbedder` the scripting (`fail(transient=...)`, `recover`, `fail_next`, `before_embed`, `batch_size`) and `FakeQdrantClient` the hooks (`on_search`, `fail_operation`, `recover`), and add `seed_chunk`, `seed_scored_chunk` and `serving_qdrant`.
  Verification: `uv run pytest tests/ai/rag/test_embedder_seam.py tests/ai/rag/test_rag_qdrant.py`
- [x] 1.2 Split `test_rag_investigator.py` into `test_investigation_context.py`, `test_investigation_pause.py` and `test_investigation_stop.py`, over the Qdrant, embedder and clock fakes.
  Verification: `uv run pytest tests/ai/rag/test_investigation_context.py tests/ai/rag/test_investigation_pause.py tests/ai/rag/test_investigation_stop.py`
- [x] 1.3 Move the cluster addressing, API key, timeout and server label tests to the Kubernetes, keyring and OTLP fakes and the loopback server, and delete the patches of `QdrantClient`, `kube_configuration` and `get_qdrant_api_key`.
  Verification: `uv run pytest tests/ai/rag/test_qdrant_cluster_addressing.py tests/ai/rag/test_qdrant_api_key_from_keyring.py tests/ai/rag/test_qdrant_timeout_setting.py tests/ai/rag/test_qdrant_server_label.py`

## 2. The retrieval and telemetry tests run on edge fakes (test-only edits)

- [x] 2.1 Move the hybrid search, filter and model compatibility tests to the Qdrant and embedder fakes. Move the BM25 cases to `tests/ai/test_lexical_ranking.py`. Delete `test_rag_rrf.py`.
  Verification: `uv run pytest tests/ai/rag/test_hybrid_search.py tests/ai/rag/test_retriever_filters.py tests/ai/rag/test_embedding_model_compatibility.py tests/ai/test_lexical_ranking.py`
- [x] 2.2 Move the query telemetry tests to the OTLP fake, and split them into stage times, collection search concurrency and Qdrant request telemetry.
  Verification: `uv run pytest tests/ai/rag/test_query_stage_telemetry.py tests/ai/rag/test_collection_search_concurrency.py tests/ai/rag/test_qdrant_request_telemetry.py tests/ai/rag/test_qdrant_collection_setup.py`

## 3. The indexer tests run on edge fakes (test-only edits)

- [x] 3.1 Split the indexer and multi-project tests into workspace indexing, multi-project indexing, purge and recovery, and failure and resume. Delete the hand-rolled Qdrant and embedder doubles and the calls of private methods.
  Verification: `uv run pytest tests/ai/rag/test_workspace_indexing.py tests/ai/rag/test_multi_project_indexing.py tests/ai/rag/test_index_purge_and_recovery.py tests/ai/rag/test_indexing_failure_and_resume.py`
- [x] 3.2 Move the drift tests to the real indexer over the fakes, and test the files that the scan skips through `detect_drift`.
  Verification: `uv run pytest tests/ai/rag/test_index_drift.py`

## 4. The embeddings tests run on edge fakes (test-only edits)

- [x] 4.1 Split `test_rag_embeddings.py` by behavior into seven files. Replace the `_MockValkey`, the patches of `_dispatch_embed` and of the node batch method, and the tests of private names with the `web`, `valkey_client` and `clock` fakes. Move the shared replies to `tests/support/embedding_replies.py` and the gateway dial double to `tests/support/fakes/gateway_dial.py`.
  Verification: `uv run pytest tests/ai/rag/test_embedding_provider_failures.py tests/ai/rag/test_embedding_providers.py tests/ai/rag/test_embedding_dimension.py tests/ai/rag/test_embedding_cache.py tests/ai/rag/test_embedding_batching.py tests/ai/rag/test_embedding_spend_records.py tests/ai/rag/test_embedding_models.py`
- [x] 4.2 Move the embedding configuration tests to the `config` fixture.
  Verification: `uv run pytest tests/ai/agents/test_embedding_config_retention.py`

## 5. The CLI, loopback and chunker tests (test-only edits)

- [x] 5.1 Dissolve `test_rag_cli.py` into CLI tests on the `cli` fixture in `tests/commands/test_ai_rag_commands.py`, with no patch.
  Verification: `uv run pytest tests/commands/test_ai_rag_commands.py`
- [x] 5.2 Move the loopback policy test of the RAG backends to public calls, and move the chat provider case to `tests/ai/client/`.
  Verification: `uv run pytest tests/ai/rag/test_example_config_loopback_rag.py tests/ai/client/test_example_config_loopback_endpoints.py`
- [x] 5.3 Add Hypothesis properties of the chunker, and rename the chunker, metadata, knowledge base and wiring tests after their behavior.
  Verification: `uv run pytest tests/ai/rag/test_chunker_properties.py tests/ai/rag/test_semantic_chunking.py tests/ai/rag/test_polyglot_chunking.py tests/ai/rag/test_metadata_extraction.py tests/ai/rag/test_knowledge_base_sync.py tests/ai/rag/test_rag_component_wiring.py`

## 6. No stale name remains (test-only edits)

- [x] 6.1 Check that no hand-rolled Qdrant, Valkey or embedder double remains in the migrated tests.
  Verification: `! git grep -n -e "class RecordingQdrant" -e "class StubQdrant" -e "class DummyQdrant" -e "class _MockValkey" -e "class StubEmbedder" -e "class FixedVectorEngine" -e "class StubFailingSecondBatchEmbedder" -e "class _BatchCountingEmbedder" -- tests/ai tests/commands`
- [x] 6.2 Check that no migrated test imports a private name of the RAG package.
  Verification: `! git grep -n -F -e "from devops_cli.ai.rag.embeddings import _" -e "from devops_cli.ai.rag.indexer import _" -e "from devops_cli.ai.rag.qdrant import _" -e "from devops_cli.ai.rag.investigator import _" -e "from devops_cli.ai.rag.retriever import _" -e "from devops_cli.ai.rag.drift import _" -- tests/ai/rag/test_embedding_cache.py tests/ai/rag/test_index_drift.py tests/ai/rag/test_investigation_context.py tests/ai/rag/test_qdrant_server_label.py tests/commands/test_ai_rag_commands.py tests/ai/agents/test_embedding_config_retention.py`

## 7. Documents (documents)

- [x] 7.1 Name the new fakes and helpers in the Qdrant and Embeddings items of `docs/TESTING.md`.
  Verification: `uv run devops ci docs`
- [x] 7.2 Check that the change folder is valid.
  Verification: `uv run devops openspec check`

## Workflow follow-up

- #1329 item 3 migrates `tests/ai/rag/test_ai_subcommands_rag.py` and the `ai/library` and command tests. #1329 item 4 rewrites the docs ingester.
- `tests/ai/rag/test_pipeline_context_budget.py` patches the pipeline, not a RAG edge. Its migration belongs with the pipeline tests of #1307.
- The default index cache is the relative path `.data/rag`. #1036 moves it under the data directory.
