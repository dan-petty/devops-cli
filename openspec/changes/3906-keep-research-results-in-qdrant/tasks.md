# Tasks

## 1. Delete points whose expiry passed in the Qdrant client

Kind: behavior. Reads: `src/devops_cli/ai/rag/qdrant.py`, `tests/support/fakes/qdrant.py`, `tests/ai/rag/test_rag_qdrant.py`, `tests/ai/rag/test_collection_search_concurrency.py`, `tests/ai/rag/test_example_config_loopback_rag.py`, `tests/ai/rag/test_index_purge_and_recovery.py`, `tests/ai/rag/test_qdrant_api_key_from_keyring.py`, `tests/ai/rag/test_qdrant_cluster_addressing.py`, `tests/ai/rag/test_qdrant_collection_setup.py`, `tests/ai/rag/test_qdrant_request_telemetry.py`, `tests/ai/rag/test_qdrant_server_label.py`, `tests/ai/rag/test_qdrant_timeout_setting.py`, `tests/ai/rag/test_query_stage_telemetry.py`, `tests/ai/rag/test_rag_ingest.py`, `tests/commands/test_rag.py`, `tests/http/test_http_egress.py`. Changes: `src/devops_cli/ai/rag/qdrant.py`, `tests/support/fakes/qdrant.py`, `tests/ai/rag/test_rag_qdrant.py`.
Adds: `delete_points_by_expiry`

- [ ] 1.1 Write test_delete_points_by_expiry in `tests/ai/rag/test_rag_qdrant.py`: it seeds one point that expires before the sweep time and one that expires after it, and asserts that the delete removes only the first
  - Verification: `$ uv run devops ci test tests/ai/rag/test_rag_qdrant.py` fails on the base
- [ ] 1.2 Add delete_points_by_expiry to QdrantProtocol and QdrantClient in `src/devops_cli/ai/rag/qdrant.py`: it deletes the points whose expires_at is earlier than the given ISO 8601 time through a qmodels.DatetimeRange condition, as delete_points_by_project deletes by payload. Add the same method to FakeQdrantClient in `tests/support/fakes/qdrant.py`, comparing the expires_at strings, so the protocol case of `tests/ai/rag/test_rag_qdrant.py` still passes
  - Verification: `$ uv run devops ci test tests/ai/rag/test_rag_qdrant.py` passes

## 2. Write a fetched research page once with the ADR payload

Kind: behavior. Reads: `src/devops_cli/ai/research/models.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/ai/page_text.py`, `src/devops_cli/ai/rag/qdrant.py`, `tests/support/fakes/qdrant.py`, `tests/ai/research/test_ai_research_analogies.py`. Changes: `src/devops_cli/ai/research/models.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/ai/research/store.py` (new), `tests/ai/research/test_research_store.py` (new).
Adds: `ResearchRecord`, `ResearchStoreError`, `ResearchStore`, `DEFAULT_RAG_RESEARCH_COLLECTION`, `from_page_text`

- [ ] 2.1 Write test_upsert_stores_the_payload, test_upsert_writes_once_for_an_equal_hash, test_upsert_updates_a_changed_text, test_upsert_refuses_a_record_without_provenance and test_upsert_refuses_a_search_result_field in `tests/ai/research/test_research_store.py`, the cases A fetched page is upserted, The same record is upserted twice, The text of a fetched page changes, A record without a source URL and A record with a title
  - Verification: `$ uv run devops ci test tests/ai/research/test_research_store.py` fails on the base
- [ ] 2.2 Add ResearchRecord to `src/devops_cli/ai/research/models.py` with the ADR payload fields, the version that the point id needs, a page field of type PageText or None, a from_page_text classmethod and extra fields allowed, so upsert can name a stray search-result field. Add DEFAULT_RAG_RESEARCH_COLLECTION with the value devops_research beside DEFAULT_RAG_DOCS_COLLECTION in `src/devops_cli/config/defaults.py`. Add ResearchStoreError and ResearchStore in `src/devops_cli/ai/research/store.py`: upsert derives a UUID version 5 from source_id and version, computes content_hash with SHA-256 of the text, refuses a blank source_url, a missing fetched_at and a title, snippet, description, rank or provider_hit field by name, scrolls the one point of the pair and writes nothing when its content_hash is equal. The store ensures the collection the way LibraryVectorStore does, through the ensure_collection call of the client
  - Verification: `$ uv run devops ci test tests/ai/research/test_research_store.py` passes

## 3. Refuse a record whose text no fetch produced

Kind: behavior. Reads: `src/devops_cli/ai/research/store.py`, `src/devops_cli/ai/research/models.py`, `src/devops_cli/ai/page_text.py`, `src/devops_cli/ai/web_search.py`, `tests/ai/agent_audit/test_store.py`. Changes: `src/devops_cli/ai/research/store.py`, `tests/ai/research/test_research_store.py`.

- [ ] 3.1 Write test_upsert_refuses_a_record_with_no_fetched_page in `tests/ai/research/test_research_store.py`, the case A record built from a search hit: a record built from a `SearchHit` of `src/devops_cli/ai/web_search.py` and no fetched page raises an error that names the missing fetch and writes no point
  - Verification: `$ uv run devops ci test tests/ai/research/test_research_store.py` fails on the base
- [ ] 3.2 Add the fetch guard to ResearchStore.upsert in `src/devops_cli/ai/research/store.py`: when the page of the record is not a PageText of `src/devops_cli/ai/page_text.py`, upsert raises ResearchStoreError with the field page before it writes anything, so a record built from a search hit of `src/devops_cli/ai/web_search.py` writes no point
  - Verification: `$ uv run devops ci test tests/ai/research/test_research_store.py` passes

## 4. Look up a research point by kind and component and hide a flagged page

Kind: behavior. Reads: `src/devops_cli/ai/research/models.py`, `src/devops_cli/ai/research/store.py`, `src/devops_cli/security/prompt_injection.py`, `tests/support/fakes/qdrant.py`, `tests/ai/research/test_ai_research_analogies.py`, `tests/ai/agent_audit/test_store.py`, `tests/ai/research/test_ai_research_marginalia.py`, `tests/ai/research/test_ai_research_mental_model.py`, `tests/ai/research/test_ai_research_socratic.py`. Changes: `src/devops_cli/ai/research/models.py`, `src/devops_cli/ai/research/store.py`, `tests/support/fakes/qdrant.py`, `tests/ai/research/test_research_store.py`.
Adds: `ResearchHit`, `lookup`

- [ ] 4.1 Write test_lookup_returns_the_url_and_date and test_lookup_hides_a_flagged_page_from_the_agent in `tests/ai/research/test_research_store.py`, the cases A query for one kind and component and A fetched page holds an injection pattern
  - Verification: `$ uv run devops ci test tests/ai/research/test_research_store.py` fails on the base
- [ ] 4.2 Add ResearchHit to `src/devops_cli/ai/research/models.py` with source_id, source_url, fetched_at, text, content_hash and score. Add lookup to ResearchStore in `src/devops_cli/ai/research/store.py`: it embeds the question with the embedder, filters by kind and component, adds the must-not condition of injection_flag when the caller is the agent, and returns each hit with its source_url and fetched_at. Upsert sets injection_flag from scan_injection_text of `src/devops_cli/security/prompt_injection.py`. Add the must_not branch to `tests/support/fakes/qdrant.py` when it is absent, so the fake applies the agent condition
  - Verification: `$ uv run devops ci test tests/ai/research/test_research_store.py` passes

## 5. Sweep the expired research points

Kind: behavior. Reads: `src/devops_cli/ai/research/store.py`, `src/devops_cli/ai/rag/qdrant.py`, `tests/support/fakes/qdrant.py`, `tests/ai/agent_audit/test_store.py`. Changes: `src/devops_cli/ai/research/store.py`, `tests/ai/research/test_research_store.py`.
Adds: `expire`

- [ ] 5.1 Write test_expire_deletes_the_point_whose_expiry_passed in `tests/ai/research/test_research_store.py`, the case One expired point and one live point
  - Verification: `$ uv run devops ci test tests/ai/research/test_research_store.py` fails on the base
- [ ] 5.2 Add expire to ResearchStore in `src/devops_cli/ai/research/store.py`: it calls delete_points_by_expiry of `src/devops_cli/ai/rag/qdrant.py` with the sweep time and returns nothing. The case seeds one expired point and one live point in `tests/support/fakes/qdrant.py` and asserts that the expired point is gone and the live point stays
  - Verification: `$ uv run devops ci test tests/ai/research/test_research_store.py` passes

## 6. Build the research store from the settings

Kind: behavior. Reads: `src/devops_cli/ai/research/store.py`, `src/devops_cli/ai/rag/indexer.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `tests/ai/agent_audit/test_store.py`. Changes: `src/devops_cli/ai/research/store.py`, `tests/ai/research/test_research_store.py`.
Adds: `from_settings`

- [ ] 6.1 Write test_from_settings_names_the_unset_qdrant_url in `tests/ai/research/test_research_store.py`, the case The Qdrant address setting is unset
  - Verification: `$ uv run devops ci test tests/ai/research/test_research_store.py` fails on the base
- [ ] 6.2 Add from_settings to ResearchStore in `src/devops_cli/ai/research/store.py`: it calls resolve_qdrant_client of `src/devops_cli/ai/rag/indexer.py` and the RAG create_embedder, so an unset qdrant.url raises ConfigurationError that names the setting and no fallback address of `src/devops_cli/config/defaults.py` is used. The case builds the store from settings with no qdrant.url and asserts that the error names qdrant.url
  - Verification: `$ uv run devops ci test tests/ai/research/test_research_store.py` passes

## 7. Show the research collection in the RAG status

Kind: behavior. Reads: `src/devops_cli/commands/rag.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/ai/rag/qdrant.py`, `tests/ai/rag/test_knowledge_base_sync.py`, `tests/commands/test_ai_rag_ingest_analyze_dry_run.py`, `tests/commands/test_rag.py`. Changes: `src/devops_cli/commands/rag.py`, `tests/ai/rag/test_knowledge_base_sync.py`.

- [ ] 7.1 Write test_rag_status_lists_the_research_collection_with_its_point_count in `tests/ai/rag/test_knowledge_base_sync.py`, the case Status runs against a Qdrant that holds the collection
  - Verification: `$ uv run devops ci test tests/ai/rag/test_knowledge_base_sync.py` fails on the base
- [ ] 7.2 Add a Research Collection row to status_cmd in `src/devops_cli/commands/rag.py`: it names DEFAULT_RAG_RESEARCH_COLLECTION of `src/devops_cli/config/defaults.py` and prints its point count from count_points, so the row names devops_research before any point exists. The case seeds one point of that collection in the qdrant fixture and asserts that the output holds the name and the count
  - Verification: `$ uv run devops ci test tests/ai/rag/test_knowledge_base_sync.py` passes

## Criteria

- Group 2: Tests that fail on the base: upsert twice with the same hash writes once; a changed hash updates; an expired point is removed by the sweep; lookup by kind and component returns the point with its URL and date.
- Group 2: A test: a point without source_url or fetched_at is refused.
- Group 4: A test: text with an injection pattern is stored with injection_flag true and lookup for the agent excludes it.
- Group 7: `devops ai rag status` shows the collection.
- Pending person: `index_doc_chunks` has a caller, or it is removed with its tests (no dead code stays)., search_code with index_doc_chunks returns one line, in the archived task list openspec/changes/archive/2026-11-12-1910-delete-unused-functions-after-manual-caller/tasks.md, and no line under src/ or tests/, so the function is already absent at the staged commit and no group can remove it; a person confirms the absence on the merged tree.
- Group 6: The Qdrant address comes from the settings, or an error names the setting (no fallback URL).

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
