# Proposal

## Why

Issue #3761 is child C of #1330. The tests of the built-in agent tools in `tests/security/test_builtin_tools.py` patch the code under test instead of its edges.

- The file holds 20 patch calls. 6 aim at process code (`run_subprocess` 5, `_run_tool_cmd` 1). 8 aim at `rag_search` (`QdrantClient.is_alive` 1, `SemanticRetriever.retrieve_context` 2, `_is_safe_workspace_path` 1, `load_settings`, `get_ai_api_key`, `get_qdrant_api_key` and a second `QdrantClient.is_alive` 1 each). 2 aim at the stdlib `time.sleep`. 4 aim at the OSV and Shodan clients (`OSVClient.query_package` 2, `ShodanInternetDBClient.check_ip` 2). The file also imports two private names, `_is_safe_workspace_path` and `_run_tool_cmd`, and builds `MagicMock` values.
- `rag_search` builds `QdrantClient` and `EmbeddingsEngine` itself. The Qdrant and embedder seams (`install_qdrant_client`, `install_embedder`) are read only by `resolve_qdrant_client` and `create_embedder`, so no fake reaches the tool.
- `FakeEmbedder` has no `embed_query`, and `EmbedderProtocol` does not declare it, although `SemanticRetriever` calls it.

## What Changes

- `rag_search` takes its Qdrant client from `resolve_qdrant_client()` and its embedder from `create_embedder(...)`. It builds no client and no engine. The replies are the same as before: an unset `qdrant.url` still gives the "unconfigured" reply, and a store that is down names its address.
- `EmbedderProtocol` declares `embed_query` and the `model` name, which the retriever and the investigator read. `FakeEmbedder` implements `embed_query` as `embed_texts([text], is_query=True)[0]`. `SemanticRetriever` takes an `EmbedderProtocol`, not the concrete `EmbeddingsEngine`, because `create_embedder` returns the protocol.
- `tests/support/fakes/qdrant.py` gets `seed_knowledge_base`, which puts the installed knowledge base digest in the docs collection, so a RAG test does not start a rebuild.
- `tests/security/test_builtin_tools.py` runs the process tools on `process_fake`, the OSV, Shodan and Radar tools on the `web` fixture, and `rag_search` on the `qdrant` and `embedder` fixtures. It holds no patch, no mock, no private import and no `time.sleep` stub. The tests of `_is_safe_workspace_path` and `_run_tool_cmd` run through `read_file`, `list_files`, `git_status`, `git_diff` and the cluster tools.
- This change alters no behavior a consumer observes. It has no spec delta, and `skip_specs: true` is set.
- This change fits one pull request. The other items of #1330 are separate changes.

## Impact

- `src/devops_cli/ai/tools/builtin_tools.py` (`rag_search`), `src/devops_cli/ai/rag/embeddings.py` (`EmbedderProtocol`) and `src/devops_cli/ai/rag/retriever.py` (one annotation).
- `tests/security/test_builtin_tools.py`, `tests/support/fakes/embeddings.py`, `tests/support/fakes/qdrant.py` and `tests/ai/rag/test_rag_embeddings.py`.
- `docs/TESTING.md`.

## Feasibility

Checked on `origin/main` 235a807c, 2026-11-06. The issue was written at 29309f04, so each claim was read again.

- The Qdrant seam exists: `install_qdrant_client` and `get_qdrant_client_override` in `ai/rag/qdrant.py`, read by `resolve_qdrant_client` in `ai/rag/indexer.py`. The embedder seam exists: `install_embedder` and `create_embedder` in `ai/rag/embeddings.py`. `rag_search` called neither (`git grep -nE "QdrantClient\(|EmbeddingsEngine\(" -- src/devops_cli/ai/tools` found two lines).
- The HTTP clients of OSV, Shodan and Radar come from `_public_api_client` in `security/vulnerability_lookup.py`, which calls the HTTP entry point. The `web` fixture answers them. `tests/security/test_vulnerability_lookup.py` already drives them this way.
- `SemanticRetriever` calls `embedder.embed_query` (`ai/rag/retriever.py`). `EmbedderProtocol` declared only `embed_texts`, and `FakeEmbedder` had no `embed_query`.
- `ensure_knowledge_base_ready` rebuilds the knowledge base when the store holds none of its points. On the fakes the rebuild works (`tests/ai/rag/test_rag_kb_sync.py`), but it prints a progress line and indexes the whole knowledge base. A seed point with the installed digest makes the check pass at once.
- The new `rag_search` tests failed on the old `rag_search`: the tool dialled `127.0.0.1:6333` and the floor refused it.
- `tests/ai/rag/test_qdrant_timeout_setting.py` builds `rag_search` with a recording client class and still passes: `resolve_qdrant_client` builds the client with `qdrant.timeout`.
- The file has no Radar patch today. This change adds one Radar case through `check_threat_intel`, because the issue asks for the Radar tool to run on the HTTP fake.

## Existing Tool Considered

No new tool is needed. The seams and fakes exist: `process_fake`, `web`, `qdrant`, `embedder` and `keyring_store`. The change calls `resolve_qdrant_client` and `create_embedder`, which are already in `ai/rag/`. The own code is one Protocol method, one fake method and one seed helper of about 20 lines. Cost: about 40,000 tokens and 2 hours to build, and about 2,000 tokens to keep. The change deletes 20 patch calls, two private imports and the direct construction of `QdrantClient` and `EmbeddingsEngine` in `rag_search`.
