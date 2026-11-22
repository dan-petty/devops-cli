# Tasks

## 1. A scroll ordered by a payload field

Kind: behavior. Reads: `src/devops_cli/ai/rag/qdrant.py`, `tests/support/fakes/qdrant.py`. Changes: `src/devops_cli/ai/rag/qdrant.py`, `tests/support/fakes/qdrant.py`, `tests/ai/rag/test_rag_qdrant.py`.

- [x] 1.1 Write the failing contract test `test_a_scroll_ordered_by_indexed_at_gives_the_newest_point_first` in `tests/ai/rag/test_rag_qdrant.py` over `contract_client` (native local mode and the fake). The collection holds three points: the first with `indexed_at` `2026-11-22T04:26:15.426174+00:00`, a second with no `indexed_at`, and a third with `2026-11-22T14:31:05.512000+00:00`. `scroll_points(name, limit=1, order_by="indexed_at", descending=True)` gives the third point, and `scroll_points(name, limit=2, order_by="indexed_at")` gives the first point and then the third. The test fails on the base, because `scroll_points` takes no `order_by`
  - Verification: `$ uv run devops ci test tests/ai/rag/test_rag_qdrant.py`
- [x] 1.2 Add the keyword arguments `order_by: str | None = None` and `descending: bool = False` to `scroll_points` of `QdrantProtocol` and of `QdrantClient`. `QdrantClient` sends `qmodels.OrderBy(key=order_by, direction=qmodels.Direction.DESC or ASC)` to the native scroll when `order_by` is set. `FakeQdrantClient.scroll_points` leaves out the points whose payload does not hold `order_by`, and sorts the others by the value
  - Verification: `$ uv run devops ci test tests/ai/rag/test_rag_qdrant.py`

## 2. A datetime index of indexed_at

Kind: behavior. Reads: `src/devops_cli/ai/rag/qdrant.py`, `src/devops_cli/config/constants.py`. Changes: `src/devops_cli/ai/rag/qdrant.py`, `src/devops_cli/config/constants.py`, `tests/ai/rag/test_qdrant_collection_setup.py`.

- [x] 2.1 Change `test_a_new_collection_gets_all_payload_indexes` and `test_an_existing_collection_without_payload_indexes_gets_all_on_the_next_run` in `tests/ai/rag/test_qdrant_collection_setup.py` to compare the field name and the field schema of each index request: `project_name` with `{"type": "keyword", "is_tenant": true}`, `file_path` and `visibility` with `keyword`, and `indexed_at` with `datetime`. The tests fail on the base, which asks for no index on `indexed_at`
  - Verification: `$ uv run devops ci test tests/ai/rag/test_qdrant_collection_setup.py`
- [x] 2.2 Add `{"field_name": "indexed_at", "field_schema": "datetime"}` to `CONST_RAG_PAYLOAD_INDEXES` in `src/devops_cli/config/constants.py`, with a comment that names #6774. In `_ensure_payload_indexes`, give `qmodels.PayloadSchemaType(spec["field_schema"])` as the schema of an entry that is not a tenant entry
  - Verification: `$ uv run devops ci test tests/ai/rag/test_qdrant_collection_setup.py`

## 3. Last Indexed shows the newest point

Kind: behavior. Reads: `src/devops_cli/commands/rag.py`. Changes: `src/devops_cli/commands/rag.py`, `tests/ai/rag/test_knowledge_base_sync.py`.

- [x] 3.1 Write the failing test `test_rag_status_shows_the_time_of_the_newest_point` in `tests/ai/rag/test_knowledge_base_sync.py`, next to the other status tests: the fake collection `devops_docs` holds a first point with `indexed_at` `2026-11-22T04:43:12.093718+00:00` and a later point with `2026-11-22T14:31:05.512000+00:00`. The output of `devops ai rag status` holds `2026-11-22 14:31:05` and does not hold `04:43:12`. The test fails on the base, which shows the first point
  - Verification: `$ uv run devops ci test tests/ai/rag/test_knowledge_base_sync.py`
- [x] 3.2 Write the test `test_rag_status_shows_no_index_time_when_qdrant_refuses_the_order`: a fake whose `scroll_points` raises `QdrantClientError` for a call with `order_by`. Status exits 0, shows `—` in "Last Indexed", and still shows the embedding model and the KB digest
  - Verification: `$ uv run devops ci test tests/ai/rag/test_knowledge_base_sync.py`
- [x] 3.3 In `_render_collection_row` of `src/devops_cli/commands/rag.py`, read "Last Indexed" from `scroll_points(coll_name, limit=1, order_by="indexed_at", descending=True)` in its own function, which gives `—` when the store raises `DevOpsCLIError`. Keep the reads of the model and of the KB digest as they are
  - Verification: `$ uv run devops ci test tests/ai/rag/test_knowledge_base_sync.py tests/ai/rag/test_rag_qdrant.py tests/ai/rag/test_qdrant_collection_setup.py`

## 4. State the source of Last Indexed

Kind: other. Reads: `src/devops_cli/ai/knowledge_base/devops_cli/tasks/rag_context_indexing.md`. Changes: `src/devops_cli/ai/knowledge_base/devops_cli/tasks/rag_context_indexing.md`.

- [x] 4.1 In the best practice list of `src/devops_cli/ai/knowledge_base/devops_cli/tasks/rag_context_indexing.md`, state that "Last Indexed" of `devops ai rag status` is the newest `indexed_at` of the collection, that Qdrant orders by the datetime index of `indexed_at`, that each index run creates that index, and that the column shows `—` until then
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
