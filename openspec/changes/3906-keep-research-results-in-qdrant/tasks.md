# Tasks

## 1. Hide and delete points whose expiry passed in the Qdrant client

Kind: behavior. Reads: `src/devops_cli/ai/rag/qdrant.py`, `tests/support/fakes/qdrant.py`, `tests/ai/rag/test_rag_qdrant.py`, `tests/ai/rag/test_collection_search_concurrency.py`, `tests/ai/rag/test_example_config_loopback_rag.py`, `tests/ai/rag/test_index_purge_and_recovery.py`, `tests/ai/rag/test_qdrant_api_key_from_keyring.py`, `tests/ai/rag/test_qdrant_cluster_addressing.py`, `tests/ai/rag/test_qdrant_collection_setup.py`, `tests/ai/rag/test_qdrant_request_telemetry.py`, `tests/ai/rag/test_qdrant_server_label.py`, `tests/ai/rag/test_qdrant_timeout_setting.py`, `tests/ai/rag/test_query_stage_telemetry.py`, `tests/ai/rag/test_rag_ingest.py`, `tests/commands/test_rag.py`, `tests/http/test_http_egress.py`. Changes: `src/devops_cli/ai/rag/qdrant.py`, `tests/support/fakes/qdrant.py`, `tests/ai/rag/test_rag_qdrant.py`.
Adds: `delete_points_by_expiry`

- [x] 1.1 Write test_delete_points_by_expiry and test_search_skips_a_point_whose_expiry_passed in `tests/ai/rag/test_rag_qdrant.py`: both seed one point whose expiry is before a given time and one point whose expiry is after it. The first asserts that the delete removes only the first point. The second asserts that a search with the range key `must_range` on the field expiry returns only the second point
  - Verification: `$ uv run devops ci test tests/ai/rag/test_rag_qdrant.py` fails on the base
- [x] 1.2 In `src/devops_cli/ai/rag/qdrant.py`, make `_build_payload_filter` read the key `must_range`, a mapping of a payload field to its `gt`, `gte`, `lt` and `lte` bounds, and build a qmodels.DatetimeRange condition for each field, beside the key `must_not`. Add delete_points_by_expiry to QdrantProtocol and QdrantClient: it deletes the points whose expiry is earlier than the given ISO 8601 UTC time through a FilterSelector, as delete_points_by_project deletes by payload. In `tests/support/fakes/qdrant.py`, add the same method to FakeQdrantClient and a `must_range` branch to `_matches_fake_filter`, comparing the stored ISO 8601 UTC strings in order, so the protocol case of `tests/ai/rag/test_rag_qdrant.py` still passes
  - Verification: `$ uv run devops ci test tests/ai/rag/test_rag_qdrant.py` passes

## 2. Write a fetched research page once for each URL with the six fields of the ADR

Kind: behavior. Reads: `src/devops_cli/ai/page_text.py`, `src/devops_cli/ai/rag/qdrant.py`, `src/devops_cli/ai/rag/embeddings.py`, `src/devops_cli/config/defaults.py`, `tests/support/fakes/qdrant.py`, `tests/support/fakes/embeddings.py`, `tests/ai/research/test_ai_research_analogies.py`. Changes: `src/devops_cli/config/defaults.py`, `src/devops_cli/ai/research/store.py` (new), `tests/ai/research/test_research_store.py` (new).
Adds: `ResearchStore`, `DEFAULT_RAG_RESEARCH_COLLECTION`, `DEFAULT_RESEARCH_EXPIRY_DAYS`

- [x] 2.1 Write test_upsert_stores_the_six_fields_of_the_adr, test_upsert_of_an_equal_hash_refreshes_the_dates and test_upsert_of_a_changed_text_replaces_the_text in `tests/ai/research/test_research_store.py`. The first asserts that the stored payload holds exactly source_url, fetch_date, content_hash, expiry, question and text, that expiry is fetch_date plus 30 days, and that content_hash is the SHA-256 of the text. The second fetches the same page again at a later time and asserts one point, the later fetch_date and expiry, and one vector write. The third fetches the same URL with another text and asserts one point with the same id and the new text, content_hash, fetch_date and expiry. They are the cases A fetched page is upserted, The same page is fetched again and The text of a fetched page changes
  - Verification: `$ uv run devops ci test tests/ai/research/test_research_store.py` fails on the base
- [x] 2.2 Add DEFAULT_RAG_RESEARCH_COLLECTION with the value devops_research beside DEFAULT_RAG_DOCS_COLLECTION, and DEFAULT_RESEARCH_EXPIRY_DAYS with the value 30, in `src/devops_cli/config/defaults.py`. Add ResearchStore in `src/devops_cli/ai/research/store.py`, built from a Qdrant client, an embedder and a collection name: upsert takes a PageText and a question. It derives the point id as a UUID version 5 of the source_url, so one URL has one point, and it ensures the collection through the ensure_collection call of the client. When the point of the URL holds the same content_hash, upsert updates fetch_date and expiry through set_payload and writes no vector. When the hash differs, or no point exists, upsert embeds the text and upserts the point with the new text, content_hash, fetch_date and expiry
  - Verification: `$ uv run devops ci test tests/ai/research/test_research_store.py` passes

## 3. Refuse a page that no fetch produced

Kind: behavior. Reads: `src/devops_cli/ai/research/store.py`, `src/devops_cli/ai/page_text.py`, `src/devops_cli/ai/web_search.py`, `tests/ai/agent_audit/test_store.py`. Changes: `src/devops_cli/ai/research/store.py`, `tests/ai/research/test_research_store.py`.

- [x] 3.1 Write test_upsert_refuses_a_search_hit_and_a_page_with_no_fetch_date_and_names_the_page_field and test_upsert_refuses_a_blank_source_url_and_names_it in `tests/ai/research/test_research_store.py`: the first passes a `SearchHit` of `src/devops_cli/ai/web_search.py`, and a plain mapping that holds a source_url and a text and no fetched_at, in place of the page, and asserts a ValidationError with the field page and no point written for each; the second passes a PageText whose source_url is blank and asserts a ValidationError with the field source_url and no point written. They are the cases A search hit in place of a page and A page with a blank source URL
  - Verification: `$ uv run devops ci test tests/ai/research/test_research_store.py` fails on the base
- [x] 3.2 Add the guard to ResearchStore.upsert in `src/devops_cli/ai/research/store.py`: when the page is not a PageText of `src/devops_cli/ai/page_text.py`, upsert raises the existing ValidationError of `src/devops_cli/exceptions/validation.py` with the field page, and when its source_url is blank it raises the same error with the field source_url, both before any write. A search hit holds a title and a snippet and no page text, so the index holds fetched pages only and no search-result field
  - Verification: `$ uv run devops ci test tests/ai/research/test_research_store.py` passes

## 4. Search the research index and leave out an expired page and a page with an injection pattern

Kind: behavior. Reads: `src/devops_cli/ai/research/store.py`, `src/devops_cli/security/prompt_injection.py`, `tests/support/fakes/qdrant.py`, `tests/support/fakes/embeddings.py`, `tests/ai/research/test_ai_research_analogies.py`, `tests/ai/agent_audit/test_store.py`, `tests/ai/research/test_ai_research_marginalia.py`, `tests/ai/research/test_ai_research_mental_model.py`, `tests/ai/research/test_ai_research_socratic.py`. Changes: `src/devops_cli/ai/research/store.py`, `tests/ai/research/test_research_store.py`.
Adds: `ResearchHit`, `search_pages`

- [x] 4.1 Write test_search_pages_returns_the_url_and_date, test_search_pages_skips_an_expired_page and test_search_pages_leaves_out_a_page_with_an_injection_pattern in `tests/ai/research/test_research_store.py`: the first asserts that a stored page comes back with its source_url and fetch_date; the second asserts that a page whose expiry is before the given time does not come back; the third stores a page whose text holds an injection pattern and asserts that the search leaves it out. They are the cases A search for a stored page, One expired page and one live page and A fetched page holds an injection pattern
  - Verification: `$ uv run devops ci test tests/ai/research/test_research_store.py` fails on the base
- [x] 4.2 Add ResearchHit to `src/devops_cli/ai/research/store.py` with source_url, fetch_date, question, text and score. Add search_pages to ResearchStore: it embeds the question with embed_query, searches the collection with a `must_range` condition that keeps only the points whose expiry is later than the given time (the current UTC time when none is given), and returns each hit with its source_url and fetch_date. It leaves out a hit whose text gives a finding to scan_injection_text of `src/devops_cli/security/prompt_injection.py`, so no stored field marks a page and the six fields of the ADR stay as they are
  - Verification: `$ uv run devops ci test tests/ai/research/test_research_store.py` passes

## 5. Sweep the expired research points

Kind: behavior. Reads: `src/devops_cli/ai/research/store.py`, `src/devops_cli/ai/rag/qdrant.py`, `tests/support/fakes/qdrant.py`, `tests/ai/agent_audit/test_store.py`. Changes: `src/devops_cli/ai/research/store.py`, `tests/ai/research/test_research_store.py`.
Adds: `expire`

- [ ] 5.1 Write test_expire_deletes_the_point_whose_expiry_passed in `tests/ai/research/test_research_store.py`: two stored pages, one whose expiry is before the given time and one after it; the sweep deletes the first and keeps the second, the case One expired point and one live point
  - Verification: `$ uv run devops ci test tests/ai/research/test_research_store.py` fails on the base
- [ ] 5.2 Add expire to ResearchStore in `src/devops_cli/ai/research/store.py`: it calls delete_points_by_expiry of `src/devops_cli/ai/rag/qdrant.py` with the given time (the current UTC time when none is given) and returns nothing. A search already skips an expired page, so the sweep only frees the space
  - Verification: `$ uv run devops ci test tests/ai/research/test_research_store.py` passes

## 6. Build the research store from the settings

Kind: behavior. Reads: `src/devops_cli/ai/research/store.py`, `src/devops_cli/ai/rag/indexer.py`, `src/devops_cli/ai/rag/library_store.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `tests/ai/agent_audit/test_store.py`. Changes: `src/devops_cli/ai/research/store.py`, `tests/ai/research/test_research_store.py`.
Adds: `build_research_store`

- [ ] 6.1 Write test_build_research_store_names_the_unset_qdrant_url in `tests/ai/research/test_research_store.py`: it builds the store from settings with no qdrant.url and asserts that the error names qdrant.url, the case The Qdrant address setting is unset
  - Verification: `$ uv run devops ci test tests/ai/research/test_research_store.py` fails on the base
- [ ] 6.2 Add build_research_store to `src/devops_cli/ai/research/store.py`, in the way that build_library_vector_store of `src/devops_cli/ai/rag/library_store.py` builds a LibraryVectorStore, which takes its client and embedder as arguments: it calls resolve_rag_components of `src/devops_cli/ai/rag/indexer.py`, so an unset qdrant.url raises ConfigurationError that names the setting and no fallback address of `src/devops_cli/config/defaults.py` is used
  - Verification: `$ uv run devops ci test tests/ai/research/test_research_store.py` passes

## 7. Show the research collection in the RAG status

Kind: behavior. Reads: `src/devops_cli/commands/rag.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/ai/rag/qdrant.py`, `tests/ai/rag/test_knowledge_base_sync.py`, `tests/commands/test_ai_rag_ingest_analyze_dry_run.py`, `tests/commands/test_rag.py`. Changes: `src/devops_cli/commands/rag.py`, `tests/ai/rag/test_knowledge_base_sync.py`.

- [ ] 7.1 Write test_rag_status_lists_the_research_collection_with_its_point_count in `tests/ai/rag/test_knowledge_base_sync.py`, the case Status runs against a Qdrant that holds the collection
  - Verification: `$ uv run devops ci test tests/ai/rag/test_knowledge_base_sync.py` fails on the base
- [ ] 7.2 Add a Research Collection row to status_cmd in `src/devops_cli/commands/rag.py`: it names DEFAULT_RAG_RESEARCH_COLLECTION of `src/devops_cli/config/defaults.py` and prints its point count from count_points, so the row names devops_research before any point exists. The case seeds one point of that collection in the qdrant fixture and asserts that the output holds the name and the count
  - Verification: `$ uv run devops ci test tests/ai/rag/test_knowledge_base_sync.py` passes

## Criteria

- Group 2: Tests that fail on the base: the same page fetched again updates fetch_date and expiry; a changed hash replaces the text; an expired point is removed by the sweep; a search returns the point with its URL and date.
- Group 3: A test: a point without source_url or fetched_at is refused.
- Group 4: A test: a search reads no expired point.
- Group 4: A test: text with an injection pattern is left out of the search for the agent.
- Group 7: `devops ai rag status` shows the collection.
- Pending person: `index_doc_chunks` has a caller, or it is removed with its tests (no dead code stays)., search_code with index_doc_chunks returns one line, in the archived task list openspec/changes/archive/2026-11-12-1910-delete-unused-functions-after-manual-caller/tasks.md, and no line under src/ or tests/, so the function is already absent at the staged commit and no group can remove it; a person confirms the absence on the merged tree.
- Group 6: The Qdrant address comes from the settings, or an error names the setting (no fallback URL).

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
