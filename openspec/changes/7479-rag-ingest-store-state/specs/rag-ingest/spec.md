## MODIFIED Requirements

### Requirement: Removed repository cleanup
The pass SHALL delete the points of each `owner/name` project held in the vector store that `service.repos` no longer lists, and MUST touch no other project.

#### Scenario: Removed repository beside a workstation project
- **WHEN** the vector store holds points for `owner/gone`, `owner/kept`, and a workstation project, `service.repos` lists only `owner/kept`, and the pass runs with a new empty data folder
- **THEN** the pass deletes the points of `owner/gone` through `delete_points_by_project` in both collections and keeps every point of `owner/kept` and the workstation project

#### Scenario: Filtered pass keeps unconfigured subset out of deletion
- **WHEN** `service.repos` lists `owner/a` and `owner/b`, `--repo owner/a` filters the pass, and the store holds points for both
- **THEN** the pass deletes no points for `owner/b`

### Requirement: Data paths containment
The checkout and indexer cache SHALL sit under `repos/<owner>/<name>` in `data.rag_dir` and MUST be resolved with `safe_resolve_subpath`, and the pass SHALL write no `state.json`.

#### Scenario: Path containment
- **WHEN** the pass writes the checkout and cache for `owner/name`
- **THEN** each path is under `data.rag_dir/repos/owner/name`, no `state.json` exists there, and a traversal path is refused

### Requirement: Atomic state write
The pass SHALL record `head`, `branch`, and `visibility` onto the project's vector store points via `set_payload` only after `index_workspace` returns.

#### Scenario: Failed run records no state
- **WHEN** the indexer raises an error after embedding part of a repository
- **THEN** no `set_payload` call records the new `head` and the next run embeds the files that were not stored

#### Scenario: A pass records the head in the store
- **WHEN** `ingest_repository` indexes `owner/name` at head `abc123` with a new empty data folder
- **THEN** Qdrant records `set_payload` for `project_name` `owner/name` with `head` `abc123`, and no `repos/owner/name/state.json` exists

### Requirement: Head check with ls-remote
The pass SHALL read the default branch and head with `git ls-remote --symref <remote> HEAD`, and MUST skip cloning and indexing when the stored head equals the remote head and `points_intact` is true.

#### Scenario: Second run at the same head
- **WHEN** a second pass runs in a new empty data folder at the head recorded in the vector store and `points_intact` returns true
- **THEN** the pass makes no `git clone`, runs no `index_workspace`, and returns `IngestResult.skipped` as `True`

#### Scenario: Re-index when points are not intact
- **WHEN** a pass runs with stored head `abc123` and `points_intact` returns `False`
- **THEN** the pass clones and calls `index_workspace` with `force=True`
