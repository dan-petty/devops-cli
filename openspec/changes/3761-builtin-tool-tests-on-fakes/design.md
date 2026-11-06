# Design

## Context

See proposal.md for the motivation and the scope (#3761, child C of #1330).

## Decisions

### 1. `rag_search` uses the seam functions
- **Decision**: the tool calls `resolve_qdrant_client()` and `create_embedder(settings.ai, api_key=...)`. Both return the installed override when a test has one, else the real object built from the settings.
- **Why**: a test then needs `install_qdrant_client` and `install_embedder` (the `qdrant` and `embedder` fixtures) and no patch.
- **Rejected**: patch `QdrantClient` and `EmbeddingsEngine` in the test. It is the patch of a name inside the code under test, which the test rules refuse.
- **Kept**: the "unconfigured" reply. `resolve_qdrant_client` raises `ConfigurationError` with the key `qdrant.url` when the address is unset. The tool turns that one error into the old reply. It lets any other `ConfigurationError` reach the tool's own catch, as before.

### 2. The reply for a store that is down names the client's address
- **Decision**: the reply reads `qdrant.base_url`, the address of the client in use. The client has the attribute, and so has the fake.
- **Rejected**: read `settings.qdrant.url` again. With an installed store the setting may be unset, and the reply would name no address.

### 3. `EmbedderProtocol` declares `embed_query`
- **Decision**: the protocol lists both calls that the code makes on an embedder. `FakeEmbedder.embed_query` is `embed_texts([text], is_query=True)[0]`.
- **Rejected**: a `hasattr` check in the retriever. The retriever calls the method without a check today, so the protocol was wrong.

### 4. A seed helper for the knowledge base
- **Decision**: `seed_knowledge_base(fake)` puts one point in the docs collection with the knowledge base project name and the installed digest. Its vector is empty, so no query finds it.
- **Rejected**: let each test run the rebuild. It indexes the whole knowledge base and prints a line, and a test that is not about the rebuild should not depend on it.
- **Rejected**: stub `ensure_knowledge_base_ready`. It is a patch of an internal name.

### 5. The private-name tests run through the public tools
- **Decision**: the symbolic-link and workspace-boundary checks run through `read_file` and `list_files`. The output, truncation and failure checks run through `git_status` and `git_diff` on `process_fake`.
- **Note**: `read_file` resolves a path before it checks it, so a link to a file inside the workspace is read, and a link to a file outside is denied. The test states that.
