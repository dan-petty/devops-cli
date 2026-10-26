# Proposal

## Why

Issue #1388: `WorkspaceIndexer` writes each project into shared Qdrant collections.
The point id hashes only the relative file path and line range.
Two projects that contain a file with the same path overwrite each other's points.
For example, lines 26-34 of this repository's `README.md` and the bundled knowledge base's `README.md` receive the identical point id.
Also, vector deletion uses `wait=False`, swallows failure, and removes cache entries before deletion finishes.
When a collection loses its points or a forced re-index runs, other projects lose their cache entries and points are not refilled.
Finally, collections lack keyword payload indexes on `project_name` (`is_tenant=True`) and `file_path`.

## What Changes

- Change point id generation to `uuid.uuid5` over `project_name`, relative path, and line range.
- Require `wait=True` on vector deletes and raise `QdrantClientError` when a delete operation fails.
- Remove `_safe_delete_points_by_files` and `delete_points_by_file`.
- Drop a cache entry in `_purge_deleted_vectors` only after its points are deleted from both collections.
- Allow `_purge_deleted_vectors` to scan for deleted files under a project when no local files remain.
- Scope `--force` re-indexing to the specified project: delete that project's points with a waited delete, drop its cache entries, and leave other projects intact.
- Write cache files atomically with `write_json_file(..., atomic=True)` and raise errors on write failure.
- Record exact point counts per scanned project and collection after each index run in `index_counts.json`.
- Detect missing or emptied project points before indexing and refill the project as `--force` does.
- Expose `WorkspaceIndexer.points_intact(project)` to verify points without scanning files.
- Create payload indexes on `project_name` (`is_tenant=True`) and `file_path` in `ensure_collection` using `CONST_RAG_PAYLOAD_INDEXES`.
- Call `ensure_collection` at index startup so existing collections receive missing payload indexes even when no files change.
- This change alters no CLI commands, options, messages, manifests, or service behavior.
- The change sets `skip_specs: true` in its `.openspec.yaml`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/config/constants.py`: Add `CONST_RAG_PAYLOAD_INDEXES` and `CONST_INDEX_COUNTS_FILENAME`.
- `src/devops_cli/ai/rag/chunker.py`: Use `uuid.uuid5(uuid.NAMESPACE_DNS, ...)` for chunk id generation.
- `src/devops_cli/ai/rag/qdrant.py`: Add `delete_points_by_project`, default `wait=True`, raise `QdrantClientError`, provision payload indexes in `ensure_collection`, and remove `delete_points_by_file`.
- `src/devops_cli/ai/rag/indexer.py`: Remove `_safe_delete_points_by_files`, update purges, implement atomic cache and count recording, and support `points_intact`.
- `src/devops_cli/commands/rag.py`: Clean up `index_counts.json` during cache clearing.
- `tests/test_rag_multi_project_indexer.py`: Add tests with fake Qdrant verifying isolation, purges, count tracking, and payload indexes.

## Feasibility

- Confirmed with standard Python library `uuid.uuid5` that distinct project names yield distinct UUIDs for identical file paths and line ranges.
- Confirmed with `qdrant_client` library source that `QdrantClient.count` supports exact counting with payload filters and raises `UnexpectedResponse` or transport errors.
- Confirmed that `qmodels.KeywordIndexParams(type="keyword", is_tenant=True)` is supported in `qdrant_client.models`.
- Confirmed `write_json_file(..., atomic=True)` in `src/devops_cli/output/file_writer.py` performs atomic writes via temporary files.

## Existing Tool Considered

We use existing maintained libraries already present in the workspace:
- Standard library `uuid.uuid5` for RFC 4122 compliant deterministic UUID generation.
- `qdrant-client` native methods (`count`, `create_payload_index`, `delete`) rather than custom implementations.
- `write_json_file` from `devops_cli.output.file_writer` for atomic file replacement.

The change deletes internal code:
- `_safe_delete_points_by_files` in `src/devops_cli/ai/rag/indexer.py`.
- `delete_points_by_file` in `src/devops_cli/ai/rag/qdrant.py`.
- Custom string formatting digest in `SemanticChunker._generate_id`.
