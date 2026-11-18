# Design

## Decisions

- **Follow ADR 0028 for the fields: source_url, fetch_date, content_hash, expiry, question and text, and no other field.**: The ADR is the accepted record, dated 2026-11-17, and its section 1 lists these six fields. The issue and the first plan listed fifteen, which the ADR does not define.
- **Keep one point for each source_url, with a UUID version 5 point id of the source_url.**: The ADR says a new hash replaces the text and keeps the URL, so the URL identifies the point, and a second write of the same URL reaches the same point with no lookup.
- **Refresh fetch_date and expiry with set_payload when the content_hash is equal, and write no vector.**: The ADR says the same hash updates fetch_date and expiry. set_payload is on QdrantProtocol, so the refresh costs no embedding.
- **Set expiry to fetch_date plus DEFAULT_RESEARCH_EXPIRY_DAYS, with the value 30.**: The ADR gives 30 days. The ADR adds no setting and no consumer needs another value, so the value is a default constant and not a new setting.
- **Add a `must_range` condition to the payload filter and delete_points_by_expiry to the client, the protocol and the fake in one group.**: `_build_payload_filter` builds equality conditions only, so neither a search nor a delete can use a date range today, and the contract case holds the fake to the protocol.
- **Leave out a page with an injection pattern when the search reads it, with scan_injection_text, and store no flag.**: The ADR fixes the six fields, so no injection_flag is stored. The scan is a pure function, and the agent never gets a page with a pattern.
- **Take a PageText and a question in upsert, and refuse anything else with the existing ValidationError that names the field.**: A search hit holds a title and a snippet and no page text, so it cannot become a point, and the payload holds no search-result field. ValidationError already carries a field, so no new error class and no change of `docs/ERRORS.md` is needed.
- **Build the store with build_research_store, which calls resolve_rag_components, and default the collection name to DEFAULT_RAG_RESEARCH_COLLECTION.**: build_library_vector_store builds a LibraryVectorStore the same way, and ADR 0028 fixes the collection name devops_research.
- **Name the methods search_pages and expire, and the builder build_research_store.**: The first plan named lookup and from_settings, which the code already defines in two other modules, so the implement job refused its Adds lines.
- **Add a Research Collection row with its point count to devops ai rag status.**: The collections table lists only the collections that Qdrant already holds, so the row names the collection before its first point.
- **Keep the searxng, duckduckgo and firecrawl chain and store fetched page text only.**: ADR 0028 section 3 fixes the chain, and the store keeps no search-result field.
- **Remove nothing for index_doc_chunks.**: search_code finds the name in no file under src or tests, so the function is already gone and a removal would change no file.

## Rejected alternatives

- **Store the fifteen fields of the issue.**: ADR 0028 is accepted and names six fields. An accepted record changes only by a recorded amendment, so a plan cannot widen the payload on its own.
- **Store injection_flag as a seventh field.**: It widens the payload that the ADR fixes. The read-time scan gives the same protection with no stored field.
- **Write no point when the hash is equal, as the issue says.**: The ADR says the same hash updates fetch_date and expiry, and a page that no round refreshes would expire although a fetch just read it.
- **A random UUID with a payload filter for the point id.**: It needs a lookup before every write and cannot guarantee one point for one URL.
- **Filter expired points after the search, in Python.**: It reads points that the search should not return, and a search with a small limit could return fewer live hits than exist. The range condition runs in Qdrant.
- **Extend LibraryVectorStore for the research collection.**: `src/devops_cli/ai/rag/library_store.py:class LibraryVectorStore` holds the library collection, its package payload and its Valkey symbol cache, which the research payload does not use.
- **Store the text of a search hit when it carries a URL and a date.**: The point would hold a snippet and no page, and the fetch rule refuses it.
- **A fallback Qdrant URL when the setting is unset.**: `src/devops_cli/config/defaults.py` holds DEFAULT_QDRANT_URL, and the issue forbids a fallback.
- **Use the Brave Search API and keep its results.**: The Brave terms forbid a store of Search Results and the API has no free tier, and ADR 0028 fixes the chain of searxng, duckduckgo and firecrawl.
- **Add a second vector database for research.**: The repository already runs Qdrant with a client wrapper, a protocol seam and an in-memory fake, so a second store would double the operations surface.

## Security

Untrusted text of a fetched web page crosses a trust boundary from the open web into the research collection and back into the agent's context, so the store keeps attacker-controlled text beside the project's own data. A person confirms that every point keeps source_url and fetch_date, that a page which is not a PageText or has a blank source_url is refused, that the search leaves out a page whose text gives a finding to scan_injection_text, that the search reads no expired point, and that the Qdrant address comes from qdrant.url and its key from the keyring or the settings, with no fallback address and no key in a payload or a log.
