# Design

## Decisions

- **Reuse web_search of the provider chain with no keep parameter.**: The owner decision of 2026-11-07 names searxng, duckduckgo and firecrawl and drops the keep flag, and the staged chain holds exactly those three providers at src/devops_cli/ai/web_search.py:293.
- **Store the page text with the URL and the date of the fetch.**: PageText carries source_url and fetched_at, and the index stores pages, not search results.
- **Freshness is the expiry together with the hash of the question and the page text.**: The expiry refreshes an old page, and the hash catches a page that changed before its expiry.
- **Refuse the query before the request, and send no masked query.**: The guard of web_search raises SearchQueryRefused before any provider runs, and SECURITY.md rule 1 forbids the leak that a masked query still allows.
- **Read the page through the page fetch boundary and never call fetch_page_text from a tool.**: The page fetch holds the https check, the named-URL check and the cap of CONST_ROADMAP_PAGE_FETCH_MAX, so the ask-mode tools keep one boundary and one fetch budget for the run.
- **Give the stage planner the two ask-mode tools through the registry and its extended prompt, with the prompt before the registry.**: The stage tools extend the investigation tools and read their names from TOOLS, and tests/roadmap/stage/test_roadmap_stage_toolbox.py:349 compares the tools of the toolbox with the names of the prompt, so a prompt that lags the registry fails that test.
- **Change the pinned tool lists of the three tests in the group that changes the registry.**: tests/roadmap/stage/test_roadmap_stage_tools.py:52 and tests/roadmap/test_roadmap_tools.py:99 pin the counts 13 and 10, and the registry that names two more tools fails them until they move in the same group.
- **Build the stage planner's ResearchAsk on a page fetch labeled stage, and never give the planner the tool fetch_page.**: The ask-mode tools need the page fetch boundary, and the requirement The tool is on for a public repository with a Crawl4AI address keeps fetch_page off the stage planner.
- **Make the per-run limit the roadmap setting roadmap.research.max_calls_per_run, with a default of 20.**: The issue asks for a setting, and the roadmap jobs read Pydantic fields under roadmap.* with a DEVOPS_CLI_ROADMAP_* variable.
- **Make the answer expiry the roadmap setting roadmap.research.answer_expiry_days, with a default of 30 days.**: The research index refreshes an expired page, and the limits table of the roadmap holds one entry per default.
- **Match the exact term with SQLite LIKE and ESCAPE and the regular expression with Python re.**: Both are in the standard library, the match is grep over the stored pages, and a test needs no file walking and no binary of its own.
- **Keep the index in a SQLite file under data.dir, at <data.dir>/research/index.sqlite3, with the fields question, text, source_url, fetched_at, content_hash and expiry.**: The roadmap jobs run on a workstation and in the Service, the file needs no cluster service, and a test doubles it with no network.
- **Deliver the measure as code in src/devops_cli/roadmap/research_measure.py, with recorded_questions and measure_research.**: The acceptance criterion asks the pull request comment to give the hit rate and the cost per question, so the change carries the code and the data rule that compute both, and a person starts the live run and writes the comment.
- **Take the recorded questions from the comment texts that the caller reads, and answer at most 10 of the last 30 days.**: The measure then needs no client of GitHub at its own call, and the caller already holds the comments of the alternatives and refine rounds.
- **Measure the candidate against the chain's web search with no index, and report the cost per question as the provider requests and the elapsed time.**: The owner wrote on 2026-11-07 that the measures of #3877 and #3915 may use any provider of the chain, and SearXNG and DuckDuckGo charge no key, so a question costs its requests and its time.
- **Regenerate the settings documents with uv run devops docs generate and no extra option.**: The generator writes docs/ENV_VARS.md and docs/CONFIGURATION.md from the settings, and the command takes no other option that the plan needs.
- **Keep the stage planner's toolset setting at base, extended and research, and raise only the tool counts of extended and research.**: The ask-mode tools belong to the toolset extended, which research already extends, so the setting gains no fourth value and the settings load keeps refusing any other value.

## Rejected alternatives

- **web_search with keep=True.**: The keep flag existed only for the Brave terms, the owner decision of 2026-11-07 drops it, and web_search takes no keep argument at src/devops_cli/ai/web_search.py:318.
- **The Crawl4AI and Kindly search tool as the ask-mode search.**: The owner decision names the provider chain as the search path, and the page fetch stays the only Crawl4AI tool.
- **Search results with title, snippet and rank in the index.**: The owner decision removes every search-result field from the payload, and the index stores pages.
- **Expiry only as the freshness rule.**: A page that changes before its expiry would answer from stale text.
- **Hash only as the freshness rule.**: A page that never changes would never refresh.
- **Mask the query and send it.**: A masked query still names a person or a host, and SECURITY.md rule 1 forbids the leak.
- **Call fetch_page_text from research_lookup.**: The page fetch holds the https check, the named-URL check and the cap of CONST_ROADMAP_PAGE_FETCH_MAX at src/devops_cli/roadmap/page_fetch.py:102, so a direct call skips the cap of 3 fetches in a run.
- **Name the two tools in the stage registry with no change to the pinned tool lists.**: tests/roadmap/stage/test_roadmap_stage_tools.py:160 compares the tools of the extended toolset with _EXTENDED_TOOL_NAMES, and tests/roadmap/test_roadmap_tools.py:99 pins the counts, so a registry change alone fails both files.
- **Change the stage registry before the extended prompt.**: tests/roadmap/stage/test_roadmap_stage_toolbox.py:349 fails when the toolbox offers a tool that the prompt does not name, so the prompt changes first.
- **Add fetch_page to the stage planner so its ask-mode tools can read a page.**: The requirement The tool is on for a public repository with a Crawl4AI address of roadmap-page-fetch says the stage planner has no fetch_page; the ask-mode tools reach the page through the page fetch boundary instead.
- **Change src/devops_cli/roadmap/stage/stage_tools.py to add the two tools.**: The stage tools read their names from the registry at src/devops_cli/roadmap/stage/stage_tools.py:488, so the inherited methods are its tools with no change to that file.
- **A second ask-mode toolset beside the existing one.**: A second path duplicates the tool budget and the masking of the first, and each job already builds one tools() method.
- **A key in .github/roadmap.toml for the per-run limit.**: That file does not exist, and the roadmap settings are Pydantic fields under roadmap.*.
- **A constant only for the per-run limit.**: The issue says that the limit is a setting.
- **SQLite FTS5 for the exact term.**: FTS5 matches tokens, not an exact substring, and the standard library build may not carry it.
- **A vector store for the retrieval.**: ADR 0005 keeps a keyed lookup with a full-text fallback and rejects a vector store for retrieval of this kind.
- **The Qdrant collection of #3906 as the store of this change.**: read_issue for #3906 answers open with status/new, and references for devops_research lists only the plan folder of that item, so no client of the collection exists at the staged commit and this change cannot read it.
- **Park the measure on a person with no code.**: The acceptance criterion asks the pull request comment to give the hit rate and the cost per question, so a task group must compute both; only the live run and the comment need a person.
- **The Firecrawl search of today as the measure baseline.**: The owner wrote on 2026-11-07 that the measures of #3877 and #3915 may use any provider of the chain, and Firecrawl answers HTTP 402 when its account has no credits.
- **A Brave search in the measure.**: The owner decision drops Brave, and its terms forbid benchmark use.

## Security

A model writes the short term of an ask-mode query, so the term is untrusted input that would leave the process to a search provider and to a page fetch. The tools send it only through the web search of the provider chain, whose guard refuses a secret, an e-mail address, a private address and an internal host name before any provider runs, and the index stores page text with the URL and date of the fetch and no field of a search result. A person confirms that a search provider and `crawl4ai.url` are set, because the tools are off without a page fetch, and that the stored page text holds no personal data. `tests/roadmap/test_roadmap_ask_tools.py` fails if a refused term reaches the fake transport, and `tests/invariants/test_committed_addresses.py` fails if a private address enters a committed file.
