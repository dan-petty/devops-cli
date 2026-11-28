# Design

## Decisions

- **Store ingest state on project points in Qdrant**: `WorkspaceIndexer.write_project_state` calls `set_payload` with `{"head": head, "branch": branch, "visibility": visibility}` filtered by `{"project_name": project}` across both `code_collection` and `docs_collection`. `WorkspaceIndexer.read_project_state` calls `scroll_points` (`limit=1`, `filter_payload={"project_name": project}`) on `code_collection` (falling back to `docs_collection`) and returns the stored `head`, `branch`, and `visibility`.
- **Write head only after indexing succeeds**: `ingest_repository` calls `write_project_state` after `repo_indexer.index_workspace` returns, so an indexing failure never records the new head.
- **Discover removed repositories from Qdrant**: `WorkspaceIndexer.list_project_names` walks `scroll_payloads(..., keys=["project_name"], page_size=_STORED_STATE_PAGE_SIZE)` across both `code_collection` and `docs_collection`. `cleanup_removed_repos` filters those names to `owner/name` repository slugs not present in the full `configured_repos` set, preserving workstation projects (single-segment names) and `CONST_RAG_KB_PROJECT`.
- **Remove `state.json`**: `ingest_repository` and `cleanup_removed_repos` no longer read, write, or glob `state.json`, and `load_repo_state` is deleted. `resolve_repo_paths` stays for `tree_dir` containment.

## Rejected alternatives

- **Keep `state.json` alongside Qdrant payloads**: Rejected because two state stores can disagree and `state.json` is lost on every pod restart (`k8s/devops/workflowtemplate-rag-ingest.yaml`).
- **Store a separate manifest point or state collection in Qdrant**: Rejected because adding a manifest point pollutes search or requires an ID scheme, and a second collection adds lifecycle management when points already carry `project_name` (`src/devops_cli/ai/rag/indexer.py:1001`).
- **Add a PersistentVolumeClaim to `rag-ingest`**: Rejected because #7479 requires state to outlive the pod without a stateful volume.
- **Call `QdrantClient` directly from `ingest.py`**: Rejected because `WorkspaceIndexer` already owns the store schema and `points_intact` (`src/devops_cli/ai/rag/indexer.py:1015`).
