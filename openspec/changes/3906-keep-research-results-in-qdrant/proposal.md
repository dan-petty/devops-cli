# Proposal

## Why

Nothing stores the results of web research, so each round searches the same question again and a result is lost when a job ends (#3906). ADR 0028, accepted on 2026-11-17 (#3877), defines the research index: one Qdrant collection, one point for each fetched page, and six fields. The first plan of this item took fifteen fields from the issue, and the implement job returned the item to New (two names of its `Adds:` lines were already defined, and its review found a payload that the ADR does not define). This plan follows the ADR. It adds a research store over Qdrant with the six fields, a write that refreshes the dates of an unchanged page, a search that reads no expired page, an expiry sweep, a fetch-only rule and a status row.

## What Changes

- Add delete_points_by_expiry to the Qdrant client, its protocol and the fake, and a `must_range` condition to the payload filter, so the sweep deletes the points whose expiry is earlier than a time and a search reads no such point.
- Add src/devops_cli/ai/research/store.py with ResearchStore.upsert, which takes a PageText of the project fetch and the question that the page answers, derives a UUID version 5 point id from the source_url, and stores source_url, fetch_date, content_hash, expiry, question and text.
- Add DEFAULT_RAG_RESEARCH_COLLECTION with the value devops_research and DEFAULT_RESEARCH_EXPIRY_DAYS with the value 30 to src/devops_cli/config/defaults.py.
- Refresh fetch_date and expiry, with no vector write, when a page has the stored content_hash, and replace the text when the content_hash changes.
- Refuse a page that is not a PageText, and a page with a blank source_url, with the existing ValidationError that names the field.
- Add ResearchStore.search_pages, which embeds the question, reads no expired point, leaves out a page whose text gives a finding to scan_injection_text, and returns source_url and fetch_date with each hit.
- Add ResearchStore.expire, which deletes every point whose expiry is earlier than the sweep time.
- Add build_research_store, which builds the store with resolve_rag_components and names qdrant.url when it is unset, with no fallback address, and add research_collection_name beside rag_collection_names.
- Add a Research Collection row with its point count to devops ai rag status.
- Remove nothing for index_doc_chunks: search_code finds the name in no file under src or tests, so the function is already gone and no dead code stays.
- Add the research-store capability to the living specs through the spec delta of this change.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `research-store`: Research payload, Same hash refreshes the dates, Changed hash replaces the text, Search reads no expired point, Expire sweep, Refuse text with no fetch, Refuse a blank source URL, Injection pattern, Status shows the collection, Qdrant address from settings

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/ai/rag/qdrant.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/ai/research/store.py`, `src/devops_cli/ai/rag/indexer.py`, `src/devops_cli/commands/rag.py`
- Tests: `tests/support/fakes/qdrant.py`, `tests/ai/rag/test_rag_qdrant.py`, `tests/ai/research/test_research_store.py`, `tests/ai/rag/test_knowledge_base_sync.py`

## Feasibility

- `docs/adr/0028-a-research-agent-composes-open-tools-and-a-research-index.md` is the record in force: it is accepted, dated 2026-11-17, and names issue 3877. Its section 1 says `One Qdrant collection holds one point for each fetched page. Its fields are source_url, fetch_date, content_hash, expiry, question and text.` It holds no search-result field, a page expires 30 days after fetch_date, and a query reads no expired point. The first plan took fifteen fields from the issue and did not check this text; this plan does.
- The ADR says `A fetch writes one point for each source_url and content_hash; the same hash updates fetch_date and expiry, and a new hash replaces the text and keeps the URL.` The two halves read two ways, so the plan keys one point to the source_url: a new hash replaces the text of that point. A person confirms this reading, or amends the ADR.
- The issue names the fields kind, component, source_id, source_license, severity, exploited, untrusted, injection_flag and reported_issue, and a rule that an equal hash writes nothing. The ADR has none of them, and its rule for an equal hash is the refresh of the dates. The criteria of the issue that this affects stay in the plan as pending person entries with the reason.
- `src/devops_cli/ai/page_text.py:class PageText` is the frozen model that fetch_page_text returns, with `source_url: str`, `text: str`, `fetched_at: AwareDatetime` and `truncated: bool`, so the fetch date is always an aware time and a record needs no fetch of its own.
- `src/devops_cli/ai/web_search.py:class SearchHit` holds a url, a title, a snippet and a provider and no page text, so a search hit is the input that the fetch rule refuses.
- `src/devops_cli/ai/rag/qdrant.py:def _build_payload_filter` builds a qmodels.MatchValue condition for each key and reads a `must_not` key, so it matches equality only and no caller can read or delete by a date range today. `QdrantProtocol` already declares set_payload, which refreshes two fields of a point with no vector write.
- `tests/support/fakes/qdrant.py:_matches_fake_filter` compares a payload value with the filter value and applies a `must_not` mapping, and has no range branch, so the group that adds the range condition adds it to the fake too.
- `src/devops_cli/ai/rag/library_store.py:class LibraryVectorStore` takes `qdrant_client: Any = None` and `embedder: Any = None` as constructor arguments, and `build_library_vector_store` builds both. The store of this plan follows that pattern: ResearchStore takes its client, its embedder and its collection name, and build_research_store builds them. The first plan wrote that LibraryVectorStore builds the client and the embedder; it does not.
- `src/devops_cli/ai/rag/indexer.py:def resolve_rag_components` builds the Qdrant client, the embedder and the collection names from the settings, and raises ConfigurationError when `qdrant.url` is unset and no client is installed, so the store has no fallback address. `rag_collection_names` builds the names from the setting `qdrant.collection_prefix`, so research_collection_name follows the same rule and the status row names the collection that the store writes.
- `src/devops_cli/exceptions/validation.py:class ValidationError` takes `message` and `field`, and holds the field in its details, so a refusal names its field with no new error class and no change of `docs/ERRORS.md`.
- `src/devops_cli/security/prompt_injection.py:def scan_injection_text` is a pure function over a text that returns a list of findings, so the search leaves a page out with no client and no network, and no stored field marks it.
- The names that the plan adds are defined nowhere at the staged commit: delete_points_by_expiry, ResearchStore, DEFAULT_RAG_RESEARCH_COLLECTION, DEFAULT_RESEARCH_EXPIRY_DAYS, ResearchHit, search_pages, expire, build_research_store and research_collection_name. The first plan named lookup and from_settings, which `src/devops_cli/ai/analyze/outlines.py` and `src/devops_cli/ai/run_store.py` already define, and the implement job refused them.
- search_code for index_doc_chunks finds no line under src or tests, so no function exists and no group removes it. search_code for the word research in `src/devops_cli/config/settings.py` finds only the description of a stage setting, so the plan adds no research setting: the ADR fixes the 30 days, and the value is a default constant.
- The cases need a client of the Qdrant service and an embedder as preconditions; each case gives `tests/support/fakes/qdrant.py:class FakeQdrantClient` and `tests/support/fakes/embeddings.py` and reaches no network. No call of the plan needs a checkout of a repository.
- The plan introduces no new program and no new command: every verify is `uv run devops ci test` with a path, and `uv`, `devops` and `pytest` are in the runner image. The first checks against the real system are `uv run devops ci test tests/ai/research/test_research_store.py` and `uv run devops ai rag status`.

## Existing Tool Considered

qdrant-client (Apache-2.0, maintained, in use in the repository) and the repository's QdrantClient wrapper cover the vector store: collection creation, upsert, payload filters, vector search, set_payload and delete. The change builds a thin store on them and reuses the RAG embedder: about 40k tokens to write it, about 15k tokens for each later fix, and about 1 day of elapsed work.

## Dependencies

None.
