# Design

## Decisions

- **Compose SearXNG, Crawl4AI, ripgrep and Qdrant behind pydantic-ai rather than adopt one research agent.**: Each part is open and maintained and covers one need, and no research agent holds the project's exact-match, egress and budget controls.
- **Store fetched page text only, with the source URL, the fetch date, a content hash, an expiry and the question that found it.**: A model summary cannot prove that an exact string exists, and a search-result field holds no page text.
- **Use ripgrep for exact and regular-expression search over the stored text, with Python `re` for text in memory.**: ripgrep returns the matching line and the file and needs no file walking or binary handling of our own.
- **Keep the chain searxng, duckduckgo, firecrawl, with no keep parameter and no allows_keep flag.**: The owner set the order on 2026-11-07, and one settings list makes the chain cheap to reverse.
- **Set the record to `status: accepted` with its body hash in the pull request, and take the owner's comment on #3877 and the merge as the approval.**: `docs/adr/README.md:40:`The merge by the owner accepts the record.`, and the item asks for the approval comment as well.
- **Take the next free record number from the records folder and quote each document span as it stands at the staging commit.**: The newest record at the staging commit is 0027, and a span copied from the staged line passes the citation check.
- **Record the measure from the run of the ten questions that the approving person records on #3877.**: A runner Job pod cannot reach SearXNG and the Firecrawl key reaches only the pod of the Service deployment, so no step of the job can run it.

## Rejected alternatives

- **GPT Researcher as the research agent.**: It covers orchestration but holds no project Qdrant schema, no exact string match and no egress or budget control.
- **The LangChain open deep research agent.**: It adds a large dependency and a model-summary path, and its answer is a summary rather than the fetched text.
- **STORM.**: It writes a long article and does not check one narrow claim on the fetched text.
- **The Brave Search API.**: Its terms forbid storing the results and it has no free tier, so the chain keeps the providers that the settings list.
- **Firecrawl alone as the search chain.**: The refine block of #3877 records HTTP 402, and the chain already falls to DuckDuckGo with no key (`docs/CONFIGURATION.md:350`).
- **Search-result fields such as title, snippet and rank in the research index.**: The index stores pages, and a search-result field holds no text that a string match can check.
- **A Python `re`-only string match.**: It needs its own file walking and binary handling, and ripgrep already returns the matching line and file.
- **A model summary as the check of a claim.**: A summary is not the text and can miss an exact string, and ADR 0005 keeps a finding on a tool and a checked fact.

## Security

A research query and the text of a fetched page cross the cluster boundary to the public providers of the search chain, and a hosted model reads the result. A query that held a secret, personal data, a private address or an internal host name would leave the cluster with it. The owner confirms two things before the record is accepted: the provider list is the one the owner set, and no recorded question holds private code, a secret, personal data or an internal host name. `tests/ai/test_web_search.py` fails when the query guard, the secret mask or the public egress level of a provider breaks, and the follow-up work keeps the egress rule of the record.
