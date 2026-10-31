# Tasks

## 1. Valkey seam protocol and methods

- [x] Add failing test asserting ValkeyProtocol methods and commands
  - Verification: `uv run pytest tests/test_valkey.py -k test_valkey_protocol`
- [x] Add ValkeyProtocol and missing methods to ValkeyClient
  - Verification: `uv run devops ci typecheck`

## 2. Qdrant seam protocol, native client injection, and fake

- [x] Add failing test asserting QdrantProtocol and fake behavior
  - Verification: `uv run pytest tests/test_rag_qdrant.py -k test_qdrant_protocol`
- [x] Add QdrantProtocol, native client support in QdrantClient, remove _build_client, and implement fake in tests/support/fakes/qdrant.py
  - Verification: `uv run pytest tests/test_rag_qdrant.py`

## 3. Embedder protocol, factory, and fake

- [x] Add failing test asserting EmbedderProtocol and fake behavior
  - Verification: `uv run pytest tests/test_rag_embeddings.py -k test_embedder_protocol`
- [x] Add EmbedderProtocol, create_embedder factory, and fake in tests/support/fakes/embeddings.py
  - Verification: `uv run pytest tests/test_rag_embeddings.py`

## 4. Root fixtures and test migrations

- [x] Register valkey, qdrant, and embedder fixtures in tests/conftest.py
  - Verification: `uv run pytest tests/test_valkey.py tests/test_rag_qdrant.py tests/test_rag_embeddings.py`
- [x] Migrate tests/test_rag_qdrant.py off MagicMock and onto shared fakes and real in-memory client
  - Verification: `uv run pytest tests/test_rag_qdrant.py`

## 5. Documentation, verification, and archive

- [x] Update docs/TESTING.md and regenerate documentation
  - Verification: `uv run devops docs generate --sync-readme`
- [x] Pass all CI checks and archive change
  - Verification: `uv run devops openspec archive 1317-valkey-qdrant-embedder-seams`

## Workflow follow-up

- Package migration items (#1326, #1327, #1328, #1329, #1330, #1331, #1332, #1334, #1335) adopt the shared fakes and seams across their test modules.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
