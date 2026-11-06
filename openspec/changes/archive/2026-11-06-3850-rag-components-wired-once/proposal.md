# Proposal

## Why

Issue #3850 is item 1 of the Fit note of #1329. Three places turn the settings into a Qdrant client, an embedder and the collection names:

- `_get_rag_components` in `commands/rag.py`. `commands/ai.py` imports it by its private name.
- `_resolve_runtime_qdrant_and_embedder` in `commands/ai_ingest.py`.
- `_get_or_create_retriever` in `ai/rag/investigator.py`. It builds `QdrantClient` and `EmbeddingsEngine` inline, so an installed Qdrant or embedder fake never reaches it.

The library vector store is wired in `commands/ai_ingest.py` (`build_runtime_vector_store`), and `commands/rag.py` holds a pass-through `load_settings`. A command should only adapt the arguments and the output. The wiring is domain logic, and a test of it should not need a command.

## What Changes

- `ai/rag/indexer.py` gains one public function, `resolve_rag_components(settings=None)`. It returns `RagComponents`: the Qdrant client, the embedder, the code collection name and the docs collection name. The Qdrant client and the embedder come from their seams (`resolve_qdrant_client`, `create_embedder`). A missing `qdrant.url` raises `ConfigurationError`.
- `resolve_qdrant_client` takes an optional `settings`, so a caller that holds settings (the investigator) gets a client built from them, not from a second load.
- `commands/rag.py`, `commands/ai.py` and `ai/rag/investigator.py` call `resolve_rag_components`. `_get_rag_components`, the inline `QdrantClient` and `EmbeddingsEngine` of the investigator, and the dead `if prefix else DEFAULT_...` branches go. The pass-through `load_settings` of `commands/rag.py` goes.
- `ai/rag/library_store.py` gains `build_library_vector_store`, next to `LibraryVectorStore` and `load_local_contracts`. It replaces `build_runtime_vector_store`, `_build_runtime_vector_store` and `_resolve_runtime_qdrant_and_embedder` of `commands/ai_ingest.py`. The alias `_load_local_contracts` (no user) goes. The store catches `DevOpsCLIError` and logs it, where the old code caught `Exception`; the swallowed-failure ceiling of `commands/ai_ingest.py` drops by one.
- A missing Qdrant address now ends a `devops ai rag` command through the one error report of the CLI (exit code 1, the same message, no traceback), where the command printed the message itself.
- `retrieve_rag_context` of `commands/ai.py` (the chat and agent flows) now skips RAG without a message when the address is missing. It used to print the same error and exit. Its `ConfigurationError` goes to the debug log, like every other failure of that function.
- Tests: `tests/ai/rag/test_rag_components.py` and `tests/ai/rag/test_library_store_wiring.py` are new. They use the `qdrant`, `embedder` and `valkey` fixtures. The tests that patched the removed names (`_get_rag_components`, `investigator.QdrantClient`, `investigator.EmbeddingsEngine`) install a double at the Qdrant and embedder seams instead.
- The change has no spec delta: no command, option, message text or request changes. `skip_specs: true` is set.
- The change fits one pull request.

## Impact

- `src/devops_cli/ai/rag/` (`indexer.py`, `investigator.py`, `library_store.py`, `__init__.py`), `src/devops_cli/commands/` (`rag.py`, `ai.py`, `ai_ingest.py`), `docs/TESTING.md`, `tests/ai/rag/`, `tests/commands/test_library_vector_tier.py`, `tests/valkey/test_valkey_cache_tier.py`, `tests/fixtures/swallowed_failures_ceilings.json`.
- Left to the other items of #1329: the migration of the 23 `ai/rag` test files, the `ai/library` and command tests, and the rewrite of the docs ingester.

## Feasibility

Checked on `origin/main` 235a807c, 2026-11-06. The text of #1329 is older than the tree, so each claim was read again.

- Three copies of the wiring exist: `rg -n "create_embedder|EmbeddingsEngine\(|resolve_qdrant_client\(|QdrantClient\(" src/devops_cli/commands src/devops_cli/ai/rag/investigator.py` finds `commands/rag.py`, `commands/ai_ingest.py` and the investigator.
- Two claims of #1329 are out of date. `load_local_contracts` is already public in `ai/rag/library_store.py` (#848), and only its alias `_load_local_contracts` remains. `commands/ai_ingest.py` no longer imports the private `commands.valkey._resolve_client`: it uses `shared_cache_tier`, which resolves the Valkey seam. So the change moves the builder of the store and drops the alias, and does nothing for the Valkey client.
- The Qdrant, embedder and Valkey seams exist (`install_qdrant_client`, `install_embedder`, `install_valkey_client`) with the root fixtures `qdrant`, `embedder` and `valkey`. The investigator did not use the first two, because it built the classes itself. After the change it does, and the check was `uv run pytest tests/ai/rag/test_rag_investigator.py tests/ai/rag/test_qdrant_timeout_setting.py`.
- `ConfigurationError` is a `DevOpsCLIError`, and every Typer command of the CLI reports a `DevOpsCLIError` it raises with the exit code of the error (`_report_devops_error`, `core/cli.py`). So a command needs no `try` for the missing address.
- The builder goes to `ai/rag/library_store.py`, not to `ai/library/`: #1329 allows both, `LibraryVectorStore` and `load_local_contracts` live there, and `ai/library/` holds the introspector, the docs ingester and the drift auditor, which do not use the store.

## Existing Tool Considered

No open tool covers this. The change moves project code into one place and adds no dependency. The cost of three copies that drift apart (the investigator already skipped the seams) is higher than the cost of the move. The change deletes `_get_rag_components`, `_resolve_runtime_qdrant_and_embedder`, `build_runtime_vector_store`, `_build_runtime_vector_store`, `_load_local_contracts`, the `load_settings` pass-through of `commands/rag.py`, and the inline client construction of the investigator.
