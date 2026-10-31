# Proposal

## Why

Issue #1317, a child of #1307 (phase D): Valkey, Qdrant and the embedder are constructed inline in multiple modules, and tests copy their own doubles. This makes the seams hard to test, the fakes hard to maintain, and the real-client behaviour unverified. This change provides one seam, one shared fake, and one contract suite for each edge.

## What Changes

- Valkey: `src/devops_cli/valkey/client.py` gains typed methods (`delete`, `mget`, `scan`, `eval`) and a `ValkeyProtocol` that defines all commands, raw execution, and pipelines that devops-cli makes. A factory and installation hook provide connected clients.
- Qdrant: `src/devops_cli/ai/rag/qdrant.py` defines a `QdrantProtocol` for wrapper calls that RAG code makes. `QdrantClient` accepts a native `qdrant_client.QdrantClient` directly. `_build_client` is removed, and `resolve_qdrant_client` in `src/devops_cli/ai/rag/indexer.py` acts as the seam factory.
- Embedder: `EmbedderProtocol` is defined next to `EmbeddingsEngine` in `src/devops_cli/ai/rag/embeddings.py` without clashing with the pydantic-ai embedder. `create_embedder` provides the factory to build the engine from settings.
- Fakes: `tests/support/fakes/qdrant.py` provides an in-memory Qdrant fake with cosine search, payload filtering, and an unreachable mode. `tests/support/fakes/embeddings.py` provides a deterministic fake with fixed vectors and provider failure modes. `tests/support/fakes/valkey.py` continues to provide the in-memory Valkey fake.
- Fixtures: `valkey`, `qdrant`, and `embedder` fixtures in `tests/conftest.py` install the fakes into the seams and clean them up at teardown.
- Contract suites: Contract tests verify real implementations and fakes raise identical exceptions and keep identical contracts. `tests/test_rag_qdrant.py` runs over `qdrant-client` in-memory mode `:memory:`, and `tests/test_rag_embeddings.py` validates engine contracts against loopback endpoints.
- This change alters no consumer-observed CLI behavior or commands, so it sets `skip_specs: true`.
- This change fits one pull request.

## Feasibility

- The `fakeredis` library is installed and provides in-memory RESP server capabilities via `FakeServer` and `FakeValkey`.
- The `qdrant-client` library supports `:memory:` location for in-process vector storage and filtering without external network or daemons.
- The standard library `http.server` and loopback sockets allow offline verification of embedder and Valkey contracts.
- Verification commands pass with all tests completing in under 1 second per test without external network access.

## Existing Tool Considered

- `fakeredis` is used for in-memory Valkey emulation.
- `qdrant-client` local memory mode is used for real in-process Qdrant contract tests.
- Cost to build instead: 500k tokens and 3 hours elapsed time. Upkeep is minimal as libraries are already pinned in `pyproject.toml`.
- The change deletes duplicated mock clients across test files, including MagicMock patching in `tests/test_rag_qdrant.py`.
