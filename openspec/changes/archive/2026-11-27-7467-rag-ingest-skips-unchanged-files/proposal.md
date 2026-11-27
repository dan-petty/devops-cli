# Proposal: #7467

## Why

Each run of the `rag-ingest` Workflow embeds every file again (#7467). The indexer skips a file only when its cache file holds the content hash of the file. WorkflowTemplate `rag-ingest` sets `DEVOPS_CLI_DATA_DIR=/home/devops/.data` on the volume `home`, which is an `emptyDir`, so each pod starts with no cache file. On 2026-11-27 the first run after #5289 took 73.5 minutes. CronWorkflow `rag-ingest` runs every 3 minutes with `concurrencyPolicy: Forbid`, so the next full run started 90 s later, and the local embedding model of the gateway got a load that did not stop.

## What Changes

- Each point holds two new payload keys: `file_hash`, the content hash of its whole file, and `file_chunks`, the count of the chunks of that version of the file. The key `content_hash` is the hash of one chunk, so it cannot show the version of a file.
- When the cache file does not hold the hash of a file, the run reads the file state of the project from Qdrant, once for each project: one paged scroll of `file_path`, `file_hash` and `file_chunks` for each collection (`QdrantClient.scroll_payloads`). The run skips a file whose points hold its current hash and whose count of points equals `file_chunks`. Each other stored file gets the incomplete marker of #1296: the run embeds it again and deletes its old points first.
- The run adds the stored files to its cache in memory, so the purge of an edited or a deleted file finds their points with no cache file.
- A failed store read stops the run before it embeds a chunk.
- The cache file stays a local speed-up: a run whose cache file holds every file reads nothing from the store.
- Points that a release before this change wrote hold no `file_hash`. The first run after the release embeds each such file once and writes the new keys. Later runs skip it.
- What a run embeds and the payload of each point change, and a consumer sees both, so the change has a delta in `rag-index`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rag-index`: each point holds the hash and the chunk count of its file; a run with no cache file skips the files that the store holds whole; the client reads payload keys page by page.

## Impact

- Code: `src/devops_cli/ai/rag/indexer.py`, `src/devops_cli/ai/rag/qdrant.py`
- Tests: `tests/ai/rag/test_index_skip_state_from_store.py`, `tests/ai/rag/test_indexing_failure_and_resume.py`, `tests/ai/rag/test_rag_qdrant.py`, `tests/ai/rag/test_qdrant_server_label.py`, `tests/support/fakes/qdrant.py`
- Documents: `docs/cheatsheets/ai_and_rag.md`
- Cluster: no manifest change. The change adds no PersistentVolumeClaim, and the schedule, the concurrency policy and the deadline of the Workflow stay.
- The change fits one pull request.

## Feasibility

- `k8s/devops/workflowtemplate-rag-ingest.yaml` mounts the volume `home` as an `emptyDir` and sets `DEVOPS_CLI_DATA_DIR=/home/devops/.data`. `WorkspaceIndexer.cache_file` lies under that folder.
- `_build_chunk_point` wrote the `content_hash` of the chunk (`SemanticChunker._make_code_chunk` hashes the text of the chunk), so the store held no version of a file before this change.
- qdrant-client 1.20.0: `QdrantClient.scroll` takes `offset` and a list of keys as `with_payload`, and returns `(records, next_page_offset)`. A probe in local mode (`location=":memory:"`) read five points over pages of two and gave only the named keys. A collection that does not exist raised `Collection missing not found`.
- `project_name` has a tenant keyword payload index (`CONST_RAG_PAYLOAD_INDEXES`), so the scroll with the project filter uses that index.

## Existing Tool Considered

qdrant-client, which the project already uses, does the read: `scroll` with a payload filter, a list of payload keys and the offset of the next page. The change adds no library and no cluster resource. It adds a client method of about 30 lines and the read of the file state of about 90 lines: about 15k tokens and 2 hours to write and test, and about 2k tokens for each later fix. It deletes no internal code: the cache file stays as the local speed-up.
