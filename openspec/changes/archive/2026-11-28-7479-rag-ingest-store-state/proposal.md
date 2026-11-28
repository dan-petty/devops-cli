# Proposal: #7479

## Why

WorkflowTemplate `rag-ingest` mounts an `emptyDir` as `DEVOPS_CLI_DATA_DIR`, so each new pod starts with an empty data folder (#7479). `ingest_repository` previously stored each repository's head in `repos/<owner>/<name>/state.json`, and `cleanup_removed_repos` discovered removed repositories by globbing `repos/*/*/state.json`. With an empty data folder, every pod run re-cloned and re-scanned unchanged repositories and never purged points of repositories removed from `service.repos`.

## What Changes

- Add `read_project_state`, `write_project_state`, and `list_project_names` to `WorkspaceIndexer` in `src/devops_cli/ai/rag/indexer.py`, using `scroll_points`, `set_payload`, and `scroll_payloads` on Qdrant.
- Update `ingest_repository` in `src/devops_cli/ai/rag/ingest.py` to read the stored `head`, `branch`, and `visibility` from `WorkspaceIndexer.read_project_state`, write them to Qdrant via `write_project_state` after `index_workspace` succeeds, and stop reading or writing `state.json` (removing `load_repo_state`).
- Update `cleanup_removed_repos` in `src/devops_cli/ai/rag/ingest.py` to compare `owner/name` project names from `WorkspaceIndexer.list_project_names` against the full `service.repos` set rather than globbing `state.json`.
- This change alters observable `devops ai rag ingest` skip, state, and cleanup behavior, so it carries a spec delta on `rag-ingest`. It fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rag-ingest`: persist repository ingest state (`head`, `branch`, `visibility`) in Qdrant point payloads and discover removed `owner/name` repositories from Qdrant instead of `state.json`.

## Impact

- Code: `src/devops_cli/ai/rag/indexer.py`, `src/devops_cli/ai/rag/ingest.py`
- Tests: `tests/ai/rag/test_rag_ingest.py`

## Feasibility

- Confirmed against `k8s/devops/workflowtemplate-rag-ingest.yaml` (volume `home` is `emptyDir`) and `src/devops_cli/ai/rag/ingest.py` (`load_repo_state`, `cleanup_removed_repos`).
- Confirmed against `src/devops_cli/ai/rag/qdrant.py`: `scroll_points`, `scroll_payloads`, `set_payload`, and `delete_points_by_project` already exist on `QdrantProtocol` and `FakeQdrantClient`, and `scroll_points` / `scroll_payloads` treat a missing collection as empty.

## Existing Tool Considered

`qdrant/qdrant` (Apache-2.0, maintained, in-use) already stores indexed chunks and supports `scroll_points`, `scroll_payloads`, `set_payload`, and `delete_points_by_project` filtered by `project_name`. Reusing per-point payloads avoids adding any volume, collection, or dependency; the three seam methods on `WorkspaceIndexer` and ingest updates cost about 6,000 tokens and 1 hour to build (~1,000 tokens per later fix). Internal code deleted: `load_repo_state` and `state.json` read/write/glob logic in `src/devops_cli/ai/rag/ingest.py`.

## Dependencies

None.
