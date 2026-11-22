# Proposal: #6774

## Why
Closes #6774. The "Last Indexed" column of `devops ai rag status` shows the `indexed_at` value of the first point that a Qdrant scroll returns. A scroll with no order returns the points in the order of their IDs. An index run writes only the chunks that changed, so the first point can come from any older run. On 2026-11-22 a full `devops ai rag index --include-kb` ended at 14:31 UTC with exit 0, and `devops ai rag status` then showed 04:26:15 for `devops_code` and 04:43:12 for `devops_docs`, the times of an earlier run.

## What Changes
- `CONST_RAG_PAYLOAD_INDEXES` gets a `datetime` payload index on `indexed_at`. `_ensure_payload_indexes` in `src/devops_cli/ai/rag/qdrant.py` creates each index with the `field_schema` of its entry. Before, it created a `keyword` index for each entry and did not read `field_schema`. Each index run ensures its two collections, so the next run creates the new index on a collection that does not have it.
- `scroll_points` of `QdrantProtocol`, of `QdrantClient` and of the test fake gets the keyword arguments `order_by` (a payload field) and `descending`. `QdrantClient` sends them to the scroll of the native client as one `OrderBy`.
- `_render_collection_row` in `src/devops_cli/commands/rag.py` reads "Last Indexed" from a scroll of one point, ordered by `indexed_at` with the newest first. When Qdrant refuses the order, because the collection does not have the datetime index yet, the column shows `—`. The model and the KB digest columns do not change.
- The column of a `devops` command and the payload indexes that a run creates are observable, so the change carries spec deltas.
- The change fits one pull request.

## Capabilities
- `rag-status`: new capability. ADDED requirement "Last Indexed shows the newest point of the collection".
- `rag-index`: ADDED requirement "Each collection holds a datetime index of indexed_at".

## Impact
- `devops ai rag status` shows the time of the newest point of each collection.
- After the upgrade, "Last Indexed" shows `—` until the next `devops ai rag index` run creates the datetime index. Qdrant builds the index over the points that the collection holds, so the run does not embed a file again for the index.
- The knowledge base page `src/devops_cli/ai/knowledge_base/devops_cli/tasks/rag_context_indexing.md` states where the time comes from.

## Feasibility
- Code: on origin/main `9dfe03e3e`, `_render_collection_row` at `src/devops_cli/commands/rag.py:460` calls `qdrant.scroll_points(coll_name, limit=1)` and reads `indexed_at` from that point. `scroll_points` at `src/devops_cli/ai/rag/qdrant.py:880` sends no order. `_build_chunk_point` at `src/devops_cli/ai/rag/indexer.py:494` writes `indexed_at` as `datetime.now(UTC).isoformat()`.
- Live store, read-only (Qdrant server 1.20.2, qdrant-client 1.20.0): `devops ai rag status` gave 2026-11-22 04:26:15 and 04:43:12. The payload schema of both collections holds only `file_path`, `project_name` and `visibility`. A scroll with `order_by=OrderBy(key="indexed_at", direction="desc")` got HTTP 400 "Wrong input: No range index for `order_by` key: `indexed_at`. Please create one to use `order_by`."
- Library: qdrant-client 1.20.0 `QdrantClient.scroll` takes `order_by: OrderBy | None`. Its local mode (`qdrant_client/local/local_collection.py`, `_scroll_by_value`) orders by the payload value and leaves out the points that do not hold the key. `qdrant_client/local/datetime_utils.py` lists the formats that Qdrant core accepts for a datetime. The format `%Y-%m-%dT%H:%M:%S.%f%z` is the format of `indexed_at`.

## Existing Tool Considered
- Qdrant (Apache-2.0, maintained, last activity 2026-11-20) and qdrant-client (Apache-2.0) are already the store and its client. The scroll of Qdrant orders by an indexed datetime payload field and returns the newest point with `limit=1`. The change uses that order and the datetime index of Qdrant, and builds no sort of its own. The alternatives check of the issue gives the verdict `in-use`.
- The change deletes no internal code. It replaces the read of the first point for "Last Indexed".
