# Tasks

## 1. Deterministic Project-Scoped Chunk IDs

- [x] Write failing tests verifying that chunk IDs include project name, use `uuid.uuid5`, and do not collide across projects sharing a file path (`uv run pytest tests/test_rag_chunker.py tests/test_rag_multi_project_indexer.py -k test_chunk_ids_scoped_by_project`).
- [x] Implement `_generate_id` with `uuid.uuid5` over `project_name`, `file_path`, `start_line`, and `end_line` in `src/devops_cli/ai/rag/chunker.py` (`uv run pytest tests/test_rag_chunker.py tests/test_rag_multi_project_indexer.py -k test_chunk_ids_scoped_by_project`).
- [x] Replace `"devops-cli-kb"` literals in `src/devops_cli/ai/rag/indexer.py` with `CONST_RAG_KB_PROJECT` (`uv run pytest tests/test_rag_indexer_retriever.py`).
- [x] Regenerate documentation and check consistency (`uv run devops docs generate --sync-readme`).

## 2. Waited Vector Deletes, Error Propagation, and Project Deletion

- [x] Write failing tests for waited vector deletes, `QdrantClientError` raising on failed deletes, and project-scoped deletes (`uv run pytest tests/test_rag_qdrant.py tests/test_rag_multi_project_indexer.py -k test_deletes_wait_and_raise`).
- [x] Implement `delete_points_by_project`, update `delete_points_by_files` to default `wait=True` and raise on error, and delete `delete_points_by_file` in `src/devops_cli/ai/rag/qdrant.py` (`uv run pytest tests/test_rag_qdrant.py`).
- [x] Delete `_safe_delete_points_by_files` and update `_purge_deleted_vectors` and `_purge_obsolete_points` in `src/devops_cli/ai/rag/indexer.py` to call `delete_points_by_files(..., wait=True)` directly (`uv run pytest tests/test_rag_multi_project_indexer.py`).
- [x] Update existing tests that mock or call `delete_points_by_file` in `tests/test_rag_qdrant.py`, `tests/test_rag_indexer_retriever.py`, and `tests/test_rag_multi_project_indexer.py` (`uv run pytest tests/test_rag_qdrant.py tests/test_rag_indexer_retriever.py tests/test_rag_multi_project_indexer.py`).
- [x] Regenerate documentation and check consistency (`uv run devops docs generate --sync-readme`).

## 3. Atomic Cache Writes, Point Counts Tracking, and Missing Points Detection

- [x] Write failing tests for atomic cache writes, failure retention, point counts recording, and intact checks (`uv run pytest tests/test_rag_multi_project_indexer.py -k test_points_intact_and_atomic_cache`).
- [x] Implement atomic cache writing using `write_json_file(..., atomic=True)` in `src/devops_cli/ai/rag/indexer.py` (`uv run pytest tests/test_rag_multi_project_indexer.py -k test_atomic_cache`).
- [x] Add `CONST_INDEX_COUNTS_FILENAME` to `src/devops_cli/config/constants.py`, record per-project point counts after indexing, and implement `points_intact` on `WorkspaceIndexer` (`uv run pytest tests/test_rag_multi_project_indexer.py -k test_points_intact`).
- [x] Scope `--force` to the target project and refill project points when lost in Qdrant (`uv run pytest tests/test_rag_multi_project_indexer.py -k test_force_scoped_and_refill`).
- [x] Remove `index_counts.json` during `devops ai rag clear` in `src/devops_cli/commands/rag.py` (`uv run pytest tests/test_rag_cli.py`).
- [x] Regenerate documentation and check consistency (`uv run devops docs generate --sync-readme`).

## 4. Collection Payload Indexes and Pre-Scan Collection Provisioning

- [x] Write failing tests for payload index provisioning on new and existing collections during index runs (`uv run pytest tests/test_rag_multi_project_indexer.py -k test_payload_indexes_provisioned`).
- [x] Define `CONST_RAG_PAYLOAD_INDEXES` in `src/devops_cli/config/constants.py` (`uv run pytest tests/test_rag_qdrant.py`).
- [x] Update `ensure_collection` in `src/devops_cli/ai/rag/qdrant.py` to create missing payload indexes using `CONST_RAG_PAYLOAD_INDEXES` (`uv run pytest tests/test_rag_qdrant.py`).
- [x] Call `ensure_collection` at the start of `WorkspaceIndexer.index_workspace` before scanning files (`uv run pytest tests/test_rag_multi_project_indexer.py -k test_payload_indexes_provisioned`).
- [x] Regenerate documentation and check consistency (`uv run devops docs generate --sync-readme`).

## 5. Verification and CI Gate

- [x] Run full test suite for multi-project indexing and RAG modules (`uv run pytest tests/test_rag_multi_project_indexer.py tests/test_rag_indexer_retriever.py tests/test_rag_qdrant.py tests/test_rag_chunker.py`).
- [x] Run fail-to-pass check to verify tests fail on unpatched code (`uv run devops ci fail-to-pass --base origin/main`).
- [x] Run full CI checks (`uv run devops ci`).

## Workflow follow-up

- Ingestion pass command `devops ai rag ingest` (#1389).
- Argo cluster workflow lane for continuous multi-repo RAG indexing (#1389 follow-up).
- Pending a person: run `devops ai rag index <checkout> --force` once to rewrite points with project-scoped UUIDs.
- Pending a person: verify `devops ai rag query` returns distinct results for repository and knowledge base files.
- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
