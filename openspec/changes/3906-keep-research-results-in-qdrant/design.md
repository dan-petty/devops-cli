# Design

## Decisions

- **Build a new ResearchStore in src/devops_cli/ai/research/store.py over the existing QdrantClient and the RAG embedder.**: LibraryVectorStore holds the library collection, its package payload and its Valkey symbol cache, which the research payload does not use.
- **Build a record only from a PageText of the project fetch, and refuse a record whose page is not a PageText.**: src/devops_cli/ai/web_search.py:class SearchHit holds a url, a title, a snippet and a provider and no page text, so a search hit cannot become a record and the index answers only from fetched pages.
- **Derive the point id as a UUID version 5 of source_id and version.**: A Qdrant point id is an unsigned integer or a UUID, and a UUIDv5 is stable, so a second upsert of the same pair reaches the same point with no lookup.
- **Compute content_hash as the SHA-256 of the stored text.**: A record cannot claim a hash that its text does not have, so the equal-hash rule compares what is stored.
- **Store version beside the ADR payload fields.**: The equal-hash check reads the one point of a source and version through a payload filter, and version is no search-result field.
- **Delete expired points with a new QdrantClient.delete_points_by_expiry, added to the protocol and to the fake in one group.**: src/devops_cli/ai/rag/qdrant.py:def _build_payload_filter builds equality conditions only, so no caller can delete by a date range today, and the contract case holds the fake to the protocol.
- **Set injection_flag from scan_injection_text and add a must-not condition on the lookup for the agent.**: The security module already detects the patterns, and a must-not condition keeps a flagged page out of the agent's context.
- **Add a Research Collection row with its point count to devops ai rag status.**: The collections table lists only the collections that Qdrant already holds, so the row names the collection before its first point.
- **Keep the searxng, duckduckgo and firecrawl chain and store fetched page text only.**: The store keeps no search-result field, so no provider gate and no keep flag is needed.
- **Remove nothing for index_doc_chunks.**: search_code finds the name only in an archived task list and no line under src/ or tests/, so the function is already gone and a removal would change no file.

## Rejected alternatives

- **Store the text of a search hit when it carries a URL and a date.**: src/devops_cli/ai/web_search.py:class SearchHit holds url, title, snippet and provider and no fetched text, so the point would hold a snippet and no page, and the fetch rule refuses it.
- **Give index_doc_chunks a caller in the research ingest.**: search_code with index_doc_chunks returned one line in an archived task list and no line under src/ or tests/, so there is no function to call.
- **Extend LibraryVectorStore for the research collection.**: src/devops_cli/ai/rag/library_store.py:class LibraryVectorStore holds the library collection, its package payload and its Valkey symbol cache, which the research payload does not use.
- **A random UUID with a payload filter for the point id.**: It needs a lookup before every write and cannot guarantee one point for one source and version.
- **Delete expired points through the existing payload filter.**: src/devops_cli/ai/rag/qdrant.py:def _build_payload_filter builds equality conditions only, so a date range never reaches Qdrant.
- **A fallback Qdrant URL when the setting is unset.**: src/devops_cli/config/defaults.py:244:DEFAULT_QDRANT_URL = "http://localhost:6333" holds the fallback address, and the issue forbids one.
- **Store the title, snippet or rank of a search hit with the page.**: The index stores fetched pages, and a search-result field adds no provenance; upsert refuses such a field by name.
- **Use the Brave Search API and keep its results.**: The Brave terms forbid a store of Search Results and the API has no free tier, and the chain of searxng, duckduckgo and firecrawl needs no key.
- **Add a second vector database for research.**: The repository already runs Qdrant with a client wrapper, a protocol seam and an in-memory fake, so a second store would double the operations surface.

## Security

Untrusted text of a fetched web page crosses a trust boundary from the open web into the devops_research collection and back into the agent's context, so the store keeps attacker-controlled text beside the project's own data. A person must confirm that every point keeps source_url, source_license and fetched_at, that a record with no fetched page is refused, that upsert sets injection_flag from scan_injection_text, that a lookup for the agent carries the must-not condition on injection_flag, and that the Qdrant address comes from qdrant.url and its key from the keyring or the settings, with no fallback address and no key in a payload or a log line. The case test_lookup_hides_a_flagged_page_from_the_agent in tests/ai/research/test_research_store.py fails if the injection rule breaks, the case test_upsert_refuses_a_record_with_no_fetched_page fails if the fetch rule breaks, and the case test_from_settings_names_the_unset_qdrant_url fails if a fallback address comes back.
