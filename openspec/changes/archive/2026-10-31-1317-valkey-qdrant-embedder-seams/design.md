# Design

## Context

Issue #1317 unifies the edges for Valkey, Qdrant, and text embeddings behind explicit seams, shared fakes, and contract suites. Tests previously constructed custom doubles and patched internal implementation details.

## Decisions

### 1. Protocols for seams

- `ValkeyProtocol` in `src/devops_cli/valkey/client.py` declares typed commands, execute, and pipeline methods.
- `QdrantProtocol` in `src/devops_cli/ai/rag/qdrant.py` declares the 8 methods that RAG code relies upon: `is_alive`, `ensure_collection`, `upsert_points`, `search_points`, `count_points`, `scroll_points`, `delete_points_by_files`, `delete_points_by_project`.
- `EmbedderProtocol` in `src/devops_cli/ai/rag/embeddings.py` declares `embed_texts` without clashing with the pydantic-ai class name.

### 2. Seam factories and installation hooks

- `resolve_valkey_client` and `install_valkey_client` in `valkey/client.py`.
- `resolve_qdrant_client` in `indexer.py` and `install_qdrant_client` in `qdrant.py`.
- `create_embedder` and `install_embedder` in `embeddings.py`.
- Fixtures `valkey`, `qdrant`, and `embedder` in `tests/conftest.py` set the hook, yield the fake, and restore the previous state at teardown.

### 3. Fakes in tests/support/fakes/

- `tests/support/fakes/qdrant.py` provides an in-memory implementation supporting cosine distance, filters, and unreachable refusal.
- `tests/support/fakes/embeddings.py` provides deterministic vectors and failure modes.
- `tests/support/fakes/valkey.py` continues to provide the in-memory Valkey server and client.

## Rejected Alternatives

- Running external Docker containers for Valkey and Qdrant in CI. Rejected: violates hermetic test rules (tests double only process edges and CI runs network-isolated).
- Passing clients down every function signature. Rejected: rewrites hundreds of call sites without architectural benefit over single seam factories.
- Using `unittest.mock` for contract suites. Rejected: mocks hide real SDK behavior differences; contract suites must test against real library code or loopback servers.
