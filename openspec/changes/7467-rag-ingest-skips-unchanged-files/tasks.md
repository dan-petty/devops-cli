# Tasks

## 1. Read payload keys page by page

Kind: behavior.

Reads: `src/devops_cli/ai/rag/qdrant.py`, `tests/support/fakes/qdrant.py`.

Changes: `src/devops_cli/ai/rag/qdrant.py`, `tests/support/fakes/qdrant.py`, `tests/ai/rag/test_rag_qdrant.py`, `tests/ai/rag/test_qdrant_server_label.py`.

- [x] 1.1 Write the contract tests of a paged payload read over local mode and the fake, a read of a missing collection, and a failed read, and watch them fail.
  - Verification: `$ uv run devops ci test tests/ai/rag/test_rag_qdrant.py tests/ai/rag/test_qdrant_server_label.py`
- [x] 1.2 Add `scroll_payloads` to `QdrantProtocol`, `QdrantClient` and the fake.
  - Verification: `$ uv run devops ci test tests/ai/rag/test_rag_qdrant.py tests/ai/rag/test_qdrant_server_label.py`

## 2. Skip the files that the store holds whole

Kind: behavior.

Reads: `src/devops_cli/ai/rag/indexer.py`, `tests/ai/rag/test_indexing_failure_and_resume.py`.

Changes: `src/devops_cli/ai/rag/indexer.py`, `tests/ai/rag/test_index_skip_state_from_store.py`, `tests/ai/rag/test_indexing_failure_and_resume.py`.

- [x] 2.1 Write the tests of a run with a new cache folder: the store holds every file, one file changed, points with no file hash, a deleted file, a failed store read, a partly stored file, and the payload keys of a point; and the test of a run whose cache file holds every file. Watch them fail.
  - Verification: `$ uv run devops ci test tests/ai/rag/test_index_skip_state_from_store.py tests/ai/rag/test_indexing_failure_and_resume.py`
- [x] 2.2 Write `file_hash` and `file_chunks` in each point, read the file state of a project at its first cache miss, and add the stored files to the cache in memory.
  - Verification: `$ uv run devops ci test tests/ai/rag/test_index_skip_state_from_store.py tests/ai/rag/test_indexing_failure_and_resume.py`

## 3. Documents

Kind: documents.

- [x] 3.1 Name the file state that the ingest reads from Qdrant in `docs/cheatsheets/ai_and_rag.md` (Incremental Updates).
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: after the release, watch two `rag-ingest` runs in a row with no change in the indexed repositories. The second run ends in less than 3 minutes, and its log and trace show no embedded chunk.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
