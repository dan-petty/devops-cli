# Tasks

## 1. Persist ingest state in Qdrant instead of state.json

Kind: behavior.

Reads: `src/devops_cli/ai/rag/indexer.py`, `src/devops_cli/ai/rag/ingest.py`, `tests/ai/rag/test_rag_ingest.py`.

Changes: `src/devops_cli/ai/rag/indexer.py`, `src/devops_cli/ai/rag/ingest.py`, `tests/ai/rag/test_rag_ingest.py`.

- [x] 1.1 Write failing tests in `tests/ai/rag/test_rag_ingest.py` covering Qdrant head/branch/visibility recording without `state.json`, skipping clone and indexing in a fresh data folder at an unchanged head, re-indexing when `points_intact` is false, not writing `head` on `index_workspace` failure, and cleaning up removed `owner/name` repos in a fresh data folder while respecting `repo_filter` and keeping workstation projects.
  - Verification: `$ uv run devops ci test tests/ai/rag/test_rag_ingest.py`
- [x] 1.2 Add `read_project_state`, `write_project_state`, and `list_project_names` to `WorkspaceIndexer`, update `ingest_repository` and `cleanup_removed_repos` in `src/devops_cli/ai/rag/ingest.py` to use them, and remove `load_repo_state` and `state.json` handling.
  - Verification: `$ uv run devops ci test tests/ai/rag/test_rag_ingest.py`

Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
