# Proposal

## Why

Nothing stores the results of web research, so each round searches the same question again and a result is lost when a job ends (#3906). The Qdrant payload holds no source URL, fetch date, hash or expiry, and no module writes a research point. This change adds a research store over Qdrant with the ADR payload, an idempotent write, a lookup for the agent, an expiry sweep, a fetch-only rule and a status row.

## What Changes

- Add delete_points_by_expiry to the Qdrant client, its protocol and the fake, so the sweep deletes the points whose expires_at is earlier than the sweep time.
- Add src/devops_cli/ai/research/store.py with ResearchStore.upsert, which builds a point from a fetched PageText and derives a UUID version 5 point id from source_id and version.
- Add ResearchRecord and ResearchHit to src/devops_cli/ai/research/models.py, and DEFAULT_RAG_RESEARCH_COLLECTION with the value devops_research beside DEFAULT_RAG_DOCS_COLLECTION.
- Refuse a record with no fetched page, no source_url, no fetched_at or a search-result field, and name the missing field or the missing fetch in the error.
- Add ResearchStore.lookup, which filters by kind and component, runs a vector search and returns source_url and fetched_at with each hit.
- Set injection_flag from scan_injection_text, and leave a flagged point out of a lookup for the agent.
- Add ResearchStore.expire, which deletes every point whose expires_at is earlier than the sweep time.
- Add ResearchStore.from_settings, which reads qdrant.url and names the setting when it is unset, with no fallback address.
- Add a Research Collection row with its point count to devops ai rag status.
- Remove nothing for index_doc_chunks: search_code finds the name only in an archived task list, so the function is already gone and no dead code stays.
- Add the research-store capability to the living specs through the spec delta of this change.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `research-store`: Research payload, Equal hash writes once, Changed hash updates the point, Expire sweep, Lookup by kind and component, Refuse a record with no provenance, Refuse a search-result field, Refuse text with no fetch, Injection flag, Status shows the collection, Qdrant address from settings

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/ai/rag/qdrant.py`, `src/devops_cli/ai/research/models.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/ai/research/store.py`, `src/devops_cli/commands/rag.py`
- Tests: `tests/support/fakes/qdrant.py`, `tests/ai/rag/test_rag_qdrant.py`, `tests/ai/research/test_research_store.py`, `tests/ai/rag/test_knowledge_base_sync.py`

## Feasibility

- The premise of the issue is confirmed by the probe line The path `src/devops_cli/ai/research/store.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/ai/agent_audit/store.py`, `src/devops_cli/roadmap/stores/store.py`. No commit in the history deleted or renamed it. list_files of `src/devops_cli/ai/research` returned `__init__.py`, `analogies.py`, `crawler.py`, `edges.py`, `marginalia.py`, `mental_model.py`, `models.py` and `socratic.py`, so the store is new code in an existing package.
- search_code with `devops_research` returned No match, so no module names or creates that collection yet.
- search_code with `injection_flag` returned No match, so the flag field is new to the payload.
- search_code with `index_doc_chunks` returned one line, `openspec/changes/archive/2026-11-12-1910-delete-unused-functions-after-manual-caller/tasks.md:15:-e index_doc_chunks`, and no line under `src/` or `tests/`; search_code with `doc_chunks` shows only the RAG indexer's own list at `src/devops_cli/ai/rag/indexer.py:407:doc_chunks: list[CodeChunk] = []`, so no `index_doc_chunks` function exists at the staged commit and no group removes it.
- `src/devops_cli/ai/page_text.py:class PageText` is the frozen model that `src/devops_cli/ai/page_text.py:def fetch_page_text` returns, with `source_url: str`, `text: str`, `fetched_at: AwareDatetime` and `truncated: bool` at lines 62 to 65, so the provenance of a record comes from a real fetch of the project and the store adds no fetch of its own.
- `src/devops_cli/ai/web_search.py:class SearchHit` holds `url`, `title`, `snippet` and `provider` at lines 76 to 79, so a search hit carries a title and a snippet and no page text, which is the record that the new fetch rule refuses.
- `src/devops_cli/ai/rag/qdrant.py:def _build_payload_filter` builds a `qmodels.MatchValue` condition for each key and reads a `must_not` key, so it matches equality only and no caller can delete by a date range; the expiry delete is new client code beside `src/devops_cli/ai/rag/qdrant.py:def delete_points_by_project`.
- `src/devops_cli/ai/rag/qdrant.py:class QdrantProtocol` declares the client methods, and `tests/ai/rag/test_rag_qdrant.py:def test_qdrant_protocol_and_fake` holds `tests/support/fakes/qdrant.py:class FakeQdrantClient` to that protocol, so the new delete method goes into the protocol, the client and the fake in one group.
- `tests/support/fakes/qdrant.py:class FakeQdrantClient` keeps each collection as a list of points with a payload; whether its `_matches_fake_filter` applies a `must_not` condition is not checked, so the group that hides a flagged page adds that condition to the fake when it is absent.
- `src/devops_cli/security/prompt_injection.py:def scan_injection_text` is a pure function over a text that returns a list of findings, so the injection flag needs no client and no network.
- `src/devops_cli/config/defaults.py:244:DEFAULT_QDRANT_URL = "http://localhost:6333"` is the fallback address that the store must not use, and `src/devops_cli/ai/rag/qdrant.py:404:base_url: str = DEFAULT_QDRANT_URL` is the default of the client constructor, so the store builds its client through `src/devops_cli/ai/rag/indexer.py:def resolve_qdrant_client`, which raises with `src/devops_cli/ai/rag/indexer.py:470:key="qdrant.url"` when the setting is empty.
- `src/devops_cli/config/defaults.py:246:DEFAULT_RAG_DOCS_COLLECTION = "devops_docs"` is the constant whose name and place the new `DEFAULT_RAG_RESEARCH_COLLECTION` follows, with the value devops_research.
- `src/devops_cli/commands/rag.py:def status_cmd` prints the RAG table and `src/devops_cli/commands/rag.py:def _render_collections_table` prints a row for each collection that `list_collections` returns, so a collection that holds no point yet needs its own row; `tests/ai/rag/test_knowledge_base_sync.py:def test_rag_status_table_displays_collection_metadata` is the case that the new case extends, with the `qdrant` and `embedder` fixtures.
- The review finding criterion_dropped for Refuse text with no fetch is answered by the added requirement Refuse text with no fetch and by group 3, which changes `src/devops_cli/ai/research/store.py` and writes the case test_upsert_refuses_a_record_with_no_fetched_page in `tests/ai/research/test_research_store.py`.
- The methods `upsert_points`, `search_points`, `scroll_points` and `count_points` of `src/devops_cli/ai/rag/qdrant.py:class QdrantClient` and the new `delete_points_by_expiry` need a client of the Qdrant service as a precondition; each case gives `tests/support/fakes/qdrant.py:class FakeQdrantClient` and reaches no network.
- `src/devops_cli/ai/rag/embeddings.py:def create_embedder` needs a client of the embedding service as a precondition; the lookup case passes a stub embedder and reaches no network.
- `src/devops_cli/ai/rag/indexer.py:def resolve_qdrant_client` sends no request and needs no checkout of a repository: it builds the client from the settings and the keyring, so the case of the unset address asserts the error before any request.
- No call of the plan needs a checkout of a repository: no group clones, reads a work tree or runs a git command.
- The plan introduces no new program and no new command: every verify is `uv run devops ci test` with a path, and `uv`, `devops` and `pytest` are in the runner image. The only failure class that a verify reports is `test`, and no other class is new. The pod runs with readOnlyRootFilesystem: true and runAsNonRoot: true, and the cases write only under the test temporary folder.
- The first checks against the real system are `uv run devops ci test tests/ai/research/test_research_store.py` and `uv run devops ai rag status`, which prints the Qdrant endpoint, each collection row and the research row with its point count.
- `docs/adr/0028-a-research-agent-composes-open-tools-and-a-research-index.md` is a file of the staged commit, from list_files of `docs/adr`, and read_issue for #3877 shows that issue closed and completed by merged pull request #6147, so the ADR is in force; the payload field list of the ADR text is not checked, and the plan takes the fields from the issue.

## Existing Tool Considered

qdrant-client (Apache-2.0, maintained, in use in the repository) and the repository's QdrantClient wrapper cover the vector store: collection creation, upsert, payload filters, vector search and delete. The change builds a thin store on them and reuses the RAG embedder: about 40k tokens to write it, about 15k tokens for each later fix, and about 1 day of elapsed work.

## Dependencies

None.
