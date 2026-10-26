# Design

## Context

`WorkspaceIndexer` stores chunks from multiple projects in two shared Qdrant collections: code and docs.
Previously, chunk IDs were hashes of only `file_path:start_line:end_line`.
Identical paths across projects collided and overwrote one another.
Deletes were executed without waiting and errors were swallowed, leaving orphan vectors.
Collection emptying was not detected because cache hits prevented re-indexing.
Finally, collections had no payload indexes configured for fast tenant and file path filtering.

## Decisions

### 1. Project-Scoped Deterministic UUIDv5 IDs

- Use standard library `uuid.uuid5(uuid.NAMESPACE_DNS, f"{project_name}:{file_path}:{start_line}:{end_line}")` for all chunk IDs.
- *Rejected alternative:* Use separate Qdrant collections per project.
  *Evidence:* Qdrant multitenancy documentation warns that separate collections per tenant waste memory and cluster resources. It recommends one shared collection with an `is_tenant` keyword index. Multi-collection search would also require fanning out queries across twice the number of repositories.

### 2. Waited Vector Deletes and Strict Error Handling

- Always send deletes with `wait=True`.
- Delete `_safe_delete_points_by_files` and `delete_points_by_file`.
- Purges call `delete_points_by_files` directly. When deletion fails, raise `QdrantClientError` and keep cache entries intact.
- Add `delete_points_by_project` for scoped project point purges.
- *Rejected alternative:* Keep un-waited deletes with silent fallback to single file deletion.
  *Evidence:* Un-waited deletes return immediately before storage updates. If a timeout occurs, the cache entry has already been dropped, leaving undeletable orphan vectors permanently in Qdrant.

### 3. Scoped Force Re-indexing

- `--force` deletes only the target project's points from both collections using `delete_points_by_project`.
- Only drop the target project's entries from the cache dictionary.
- *Rejected alternative:* Reset the cache dictionary to empty on `--force`.
  *Evidence:* Wiping the entire cache forces every other repository sharing the collection to re-embed all files on its next run, causing thousands of redundant embedding requests.

### 4. Separate Point Counts File and Intact Check

- Store exact point counts per scanned project and collection in `index_counts.json` beside `index_cache.json`.
- Before scanning, compare current counts with recorded counts using `count_points`.
- Refill the project as `--force` does if a collection that previously held points now has zero points, or if cached files exist with zero points across both collections.
- Expose `points_intact(project)` on `WorkspaceIndexer`.
- *Rejected alternative:* Use drift's `_count_collection_project_points`.
  *Evidence:* Drift's helper returns 0 on errors, which would trigger a complete re-embed on transient connection failures. `count_points` raises `QdrantClientError` on network or server errors, preventing accidental re-indexing.
- *Rejected alternative:* Store counts directly in `index_cache.json`.
  *Evidence:* `index_cache.json` is a flat key-value map of `project:relative_path -> content_hash`. Inserting metadata objects breaks purge logic that parses cache keys.

### 5. Collection Payload Index Provisioning

- Define `CONST_RAG_PAYLOAD_INDEXES` in `src/devops_cli/config/constants.py`.
- In `ensure_collection`, create keyword indexes for `project_name` (`is_tenant=True`) and `file_path`.
- Check existing `payload_schema` and add any missing index to existing collections.
- Call `ensure_collection` at the start of indexing before inspecting file changes.
- *Rejected alternative:* Create payload indexes only inside `upsert_points`.
  *Evidence:* A clean workspace where all files are already cached does not upsert points, so collections would never receive required payload indexes.
