# Tasks

## 1. The upsert span names its server by host and port

- [x] Add failing tests: the `qdrant.upsert_points` span for an HTTP URL with userinfo and a path, a URL with a port, a user name alone with no port, and four Service addresses holds only the host (or Service DNS name) and the port
  - Verification: `uv run devops ci test tests/test_rag_qdrant_span.py`
- [ ] Add `QdrantClient._server_span_attributes`, use it for the span, and delete the `str(self.base_url)` attribute
  - Verification: `uv run devops ci test tests/test_rag_qdrant_span.py tests/test_rag_qdrant.py`
- [ ] Regenerate the documentation that the change touches: it changes no command, option or MCP tool
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 2459-qdrant-span-host-label`
