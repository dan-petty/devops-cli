# Proposal

## Why

Issue #3862 is item 2 of the Fit note of #1329. The tests of `src/devops_cli/ai/rag/` still double devops-cli code, not edges. The RAG wiring (item 1, #3850) and all shared fakes exist, so the tests can use them now.

The tree at `origin/main` 05511ed6 holds these facts. They were counted again with an AST pass over `tests/ai/rag/`, `tests/ai/test_rag_chunker.py` and `tests/ai/agents/test_embedding_config_retention.py`, because the text of #1329 is older than the tree.

- 128 patch sites (91 without the environment variables), 21 imports of a private name from devops_cli, 10 hand-rolled doubles and 4 module-level `CliRunner()` calls, in 29 files. #1329 counted 107 devops_cli patch sites, 23 private imports and 14 doubles in 27 files. Item 1 and earlier work already changed some of them.
- Six files named in #1329 no longer exist: `test_rag_aimd.py` and `test_rag_reranker.py` were deleted earlier, and `test_embedding_cache.py` and `test_review_embeddings_unserved.py` were folded into other files. The Qdrant contract suite `test_rag_qdrant.py` is done and stays as it is.
- The hand-rolled doubles are: `FakeQdrantClient` (twice), `RecordingQdrant` (twice), `StubFailingSecondBatchEmbedder`, `_BatchCountingEmbedder`, `FakeEmbedder` (an `EmbeddingsEngine` subclass), `FixedVectorEngine`, `StubEmbedder`, `StubQdrant`, `DummyQdrant`, `_MockValkey`, and the dial double `_Gateway` with `_GatewayConnection`.
- Files are named after a source module or after the work that made them (`test_rag_*`), and `test_rag_error_branches` is a catch-all.
- The chunkers have only example tests.

## What Changes

- Every test of this item doubles an edge through its shared fake: Qdrant (`qdrant`), the embedder (`embedder`), Valkey (`valkey_server`, `valkey_client`), HTTP (`web`), the clock (`clock`), OTLP (`otlp`), the keyring (`keyring_store`), the Kubernetes API (`cluster`) and the process runner (`process_fake`). No migrated test patches a devops_cli name or imports a private name. The only patches left are `monkeypatch` of environment variables, `monkeypatch.chdir`, and `os.replace` (a standard library edge) in one test.
- The shared fakes grow the scripting that the tests need:
  - `FakeEmbedder` (`tests/support/fakes/embeddings.py`) gains `fail(transient=...)`, `recover`, `fail_next`, `before_embed` and `batch_size`.
  - `FakeQdrantClient` gains `on_search`, `fail_operation` and `recover`, and records `wait` on deletes. `seed_chunk` and `seed_scored_chunk` put a chunk in a collection, and `seed_knowledge_base` can name the embedding model.
  - `serving_qdrant` is a new loopback server of the REST calls that list collections, set up a collection and query points. It shows what the real native client sends and retries: the API key header, the proxy prefix of a cluster address, quantization, payload indexes and the retry of a dropped connection.
  - `tests/support/embedding_replies.py` holds the gateway and Ollama replies and the engines that the embedding tests share. `tests/support/fakes/gateway_dial.py` is the gateway dial double that was a private class in the old test file.
- The tests are split by behavior:
  - Investigation: `test_investigation_context.py`, `test_investigation_pause.py`, `test_investigation_stop.py`.
  - Qdrant client: `test_qdrant_cluster_addressing.py`, `test_qdrant_api_key_from_keyring.py`, `test_qdrant_timeout_setting.py`, `test_qdrant_server_label.py`, `test_qdrant_collection_setup.py`, `test_qdrant_request_telemetry.py`.
  - Retrieval: `test_hybrid_search.py`, `test_retriever_filters.py`, `test_query_stage_telemetry.py`, `test_collection_search_concurrency.py`, `test_embedding_model_compatibility.py`.
  - Indexing: `test_workspace_indexing.py`, `test_multi_project_indexing.py`, `test_index_purge_and_recovery.py`, `test_indexing_failure_and_resume.py`, `test_index_drift.py`.
  - Embeddings: `test_embedder_seam.py`, `test_embedding_provider_failures.py`, `test_embedding_providers.py`, `test_embedding_dimension.py`, `test_embedding_cache.py`, `test_embedding_batching.py`, `test_embedding_spend_records.py`, `test_embedding_models.py`.
  - Other: `test_example_config_loopback_rag.py`, `test_semantic_chunking.py`, `test_polyglot_chunking.py`, `test_metadata_extraction.py`, `test_knowledge_base_sync.py`, `test_rag_component_wiring.py`.
- `test_rag_cli.py` dissolves. Its parsing, output and exit-code cases become CLI tests in `tests/commands/test_ai_rag_commands.py` on the `cli` fixture, over the fakes, with no patch. The drift cases there run the real detector.
- `tests/ai/test_lexical_ranking.py` takes the BM25 cases of the old hybrid search file, and `tests/ai/client/test_example_config_loopback_endpoints.py` takes the chat-provider case of the loopback file. Both files are outside this item's package, and their migration belongs to their own packages.
- `tests/ai/rag/test_chunker_properties.py` holds Hypothesis properties of the chunker: the chunks cover every line of text, hold the lines of their range, span no more lines than the window, overlap by the overlap, hold no more tokens than the limit and have stable unique ids; every Python function is a symbol; a heading in a code fence is not a heading. Each property sets a small `max_examples`, and no property depends on time.
- Tests that checked a private class or function are replaced by tests of the public behavior or are deleted:
  - `_EmbeddingLRUCache` unit tests: replaced by an eviction test of the engine with `cache_size=2`. The hit and miss counters stay covered by the cache lookup counter tests.
  - The tests of `_build_quantization_config`, `_execute_with_retry`, `_load_cache`, `_load_counts` and `_scan_file_drift`: replaced by tests of the real client against `serving_qdrant`, and by tests of the index run and the drift detector. The two payload-index tests of the old multi-project file tested the hand-rolled double itself. They are replaced by two tests of the real client.
  - The search dimension mismatch test of the old compatibility file: the contract suite `test_rag_qdrant.py` already holds it.
  - The cache key tests of the old server label file read a private dictionary: dropped. The behavior stays in the compatibility file (two servers with one label are checked against their own model).
  - `test_rag_rrf.py` repeated the fusion tests of the hybrid search file: deleted.
- The change has no spec delta and changes nothing under `src/`: tests, test support and one document. `skip_specs: true` is set.
- The change fits one pull request.

## Impact

- `tests/ai/rag/`, `tests/ai/agents/test_embedding_config_retention.py`, `tests/ai/test_lexical_ranking.py`, `tests/ai/client/test_example_config_loopback_endpoints.py`, `tests/commands/test_ai_rag_commands.py`, `tests/support/fakes/embeddings.py`, `tests/support/fakes/qdrant.py`, `tests/support/fakes/gateway_dial.py`, `tests/support/embedding_replies.py` and `docs/TESTING.md`.
- Counts in this item's scope, before and after:

| | Before | After |
| :--- | ---: | ---: |
| Tests (collected) | 329 | 356 |
| Patch sites, without the environment variables | 91 | 0 |
| Private imports from devops_cli | 20 | 0 |
| Hand-rolled doubles | 10 | 0 |
| Module-level `CliRunner()` in the migrated files | 2 | 0 |

  The counts are of the files this item migrates. Two files of `tests/ai/rag/` stay as they are: `test_ai_subcommands_rag.py` (item 3 of #1329) and `test_pipeline_context_budget.py`, which patches the pipeline and not a RAG edge. One standard library patch stays in `test_index_purge_and_recovery.py`: `os.replace`, which makes the atomic write of the index cache fail.
- The mutation check ran on a copy of the repository in a scratch directory. Each of these 15 changes of product code made at least one migrated test fail:

| Change of product code | Failing file |
| :--- | :--- |
| An unserved model no longer stops RAG | `test_investigation_stop.py` |
| A transient failure stops RAG too | `test_investigation_pause.py`, `test_investigation_stop.py` |
| Fusion ignores the sparse ranking | `test_hybrid_search.py` |
| Lockfiles are indexed | `test_workspace_indexing.py` |
| A purge delete does not wait | `test_index_purge_and_recovery.py` |
| The Qdrant retry backoff does not grow | `test_qdrant_request_telemetry.py` |
| The node backoff does not double | `test_embedding_batching.py` |
| The memory cache holds ten times its size | `test_embedding_cache.py` |
| The chunk window steps by its whole size | `test_chunker_properties.py` |
| A chunk window is one line too long | `test_chunker_properties.py` |
| A heading in a code fence counts | `test_chunker_properties.py` |
| The drift score is always zero | `test_index_drift.py` |
| `rag clear` deletes nothing | `test_ai_rag_commands.py` |
| A cluster address is dialled as a plain URL | `test_qdrant_cluster_addressing.py` |
| New collections are not quantized | `test_qdrant_collection_setup.py` |

## Feasibility

Checked on `origin/main` 05511ed6, 2026-11-07. The text of #1329 is older than the tree, so each claim was read again.

- The seams and fakes that the Fit note lists exist: `ls tests/support/fakes` shows `qdrant.py`, `embeddings.py`, `valkey.py`, `http.py`, `clock.py`, `otlp.py`, `keyring.py`, `kubernetes.py` and `process.py`, and `docs/TESTING.md` names each one.
- The count of #1329 is out of date. `uv run python` with an AST pass over the files gave the numbers in "Why". Some of the 27 files moved to `tests/ai/rag/` or were deleted.
- `EmbeddingsEngine` already sends all its requests through the HTTP entry point, so the `web` fixture serves every provider test. No product code needs to change. The Valkey tier takes the `valkey_client` fixture through its `valkey_client` argument.
- The real native Qdrant client cannot show quantization or payload indexes in its in-memory mode (the mode drops both), and its HTTP transport is `httpx`, not `httpx2`, so the `web` fixture does not see it. A loopback server is the way to show what it sends. The floor allows a loopback server that the test binds. The contract suite already runs the in-memory client.
- `time.perf_counter` and `time.monotonic` are not patched by `time-machine`. So the stage durations of the RAG histogram cannot be set. The new test checks the stages and outcomes, and that the total is not less than the sum of the stages.
- The default index cache is the relative path `.data/rag`, so a CLI test that indexes writes to the working directory. The new CLI tests change into `tmp_path`. #1036 moves that default under the data directory and is not part of this item.
- The mutation check above was the proof that the migrated tests keep the coverage of the old ones.

## Existing Tool Considered

Hypothesis (a dev dependency already) covers the property tests of the chunker, and the shared fakes of #1317, #1314, #1318, #1319 and #1320 cover the edges. No new tool or library is added. The change builds two small test support pieces, `serving_qdrant` and `seed_scored_chunk`, because no open tool serves the Qdrant REST calls that the real client makes, and the in-memory mode of the native client cannot show them. The cost: about 12,000 tokens to build both and fix them over two rounds, about 1,000 tokens a year to keep them, and about one hour of elapsed time. The loopback server has about 90 lines and follows the pattern of `serving_valkey`. The change deletes the 10 hand-rolled doubles listed above, the `_Gateway` dial double of the old embeddings test file (moved to the shared fakes), and the tests of private names.
