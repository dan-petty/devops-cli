---
status: accepted
date: 2026-11-17
decision-makers: [owner]
issue: 3877
body-hash: "7951ba26f96df3bd243ff6a778eb6c031642ea7450f2064f465a245a745dedb3"
---

# A research agent composes open tools and a research index

## Context and Problem Statement

The roadmap jobs search the web with one chain and keep no answer (`src/devops_cli/ai/web_search.py`). Refine, the alternatives check and the stage planner ask the same questions every round (`docs/roadmap/alternatives.md`, `docs/roadmap/stage.md`). The chain is `searxng`, `duckduckgo`, `firecrawl` (`docs/CONFIGURATION.md`), and Firecrawl answered HTTP 402 for #3877. A runner Job pod cannot reach SearXNG (`docs/CLUSTER.md`), and the Firecrawl key reaches only the Service pod (`k8s/README.md`). The project needs one design that stores fetched page text, matches an exact string, and keeps the egress and budget rules.

## Considered Options

- **SearXNG** (`docs/CLUSTER.md`, "SearXNG"; `src/devops_cli/ai/web_search.py`): an open metasearch engine with no key and no store. It lacks a fetch, a store and an exact match: chosen.
- **Crawl4AI** (`docs/CLUSTER.md`, "Crawl4AI"; `src/devops_cli/ai/page_text.py`): an open (Apache-2.0) service that returns the text of a page. It lacks a search, a store and an exact match: chosen.
- **ripgrep** (its `GUIDE.md` and `rg --help`): an open line search that returns the matching line and file. It lacks a fetch, a store and a network: chosen.
- **Qdrant** (`docs/CLUSTER.md`, "Qdrant"; `llm/qdrant-api-key`): an open vector store that the cluster runs. It lacks an exact match and a fetch: chosen.
- **pydantic-ai** (`pyproject.toml`; `src/devops_cli/ai/`): the open agent framework of the project. It lacks a research index and a search chain: chosen.
- **GPT Researcher** (its `README.md` and `gpt_researcher/agent.py`): an open deep-research agent that plans, searches and reports. It lacks the project's Qdrant schema, exact match, egress and budget: rejected, because its report is a summary and keeps no fetched text that a string match can check.
- **The LangChain open deep research agent** (`langchain-ai/open_deep_research`, `deep_researcher.py`): an open LangGraph agent that writes a report. It lacks a small dependency and a text store: rejected, because it adds a large dependency and returns a summary, not the text.
- **STORM** (`stanford-oval/storm`, `knowledge_curation.py`): an open article generator. It lacks a narrow claim check: rejected, because it writes a long article and checks no exact string on a page.
- **The Brave Search API** (its terms): a hosted search API. It lacks a permission to store results and a free tier: rejected, because its terms forbid storing results and it has no free tier.
- **Firecrawl alone** (`src/devops_cli/ai/web_search.py`; `docs/CONFIGURATION.md`): a hosted search and fetch with a key. It lacks a working key here: rejected, because #3877 records HTTP 402 and the chain falls to DuckDuckGo with no key.
- **The chain `searxng`, `duckduckgo`, `firecrawl`** (`src/devops_cli/ai/web_search.py`): the providers that the settings list. It has no `keep` parameter: chosen.
- **A model summary as the check** (ADR 0005): rejected, because a summary can miss an exact string.
- **Search-result fields in the index**: rejected, because a search-result field holds no page text to match.

## Decision Outcome

Chosen option: "SearXNG for search, Crawl4AI for fetch and extraction, ripgrep for exact and regular-expression match, and Qdrant for the research index behind pydantic-ai", because each part is open and maintained, covers one need, and no research agent holds the exact-match, egress and budget controls.

### 1. The research index

One Qdrant collection holds one point for each fetched page. Its fields are `source_url`, `fetch_date`, `content_hash`, `expiry`, `question` and `text`. It holds no search-result field: no title, snippet or rank. A page expires 30 days after `fetch_date`, and a query reads no expired point. A fetch writes one point for each `source_url` and `content_hash`; the same hash updates `fetch_date` and `expiry`, and a new hash replaces the text and keeps the URL. The index stores the fetched page text only, never a model summary.

### 2. The string-match tool

`ripgrep` reads the stored text on disk, and Python `re` reads text in memory. Each match returns the line and the file, so a claim cites its source.

### 3. The search chain

The chain is `searxng`, `duckduckgo`, `firecrawl`, in that order (`search.providers`). It has no `keep` parameter and no `allows_keep` field.

### Confirmation

`tests/invariants/test_adr_records.py` checks the form and the index of this record, and the alternatives check reads it with `src/devops_cli/roadmap/adr.py`.

## Limits

- **Egress.** Rule 2 of `SECURITY.md` sends each request through `devops_cli.http.entry` at the public level, and the query guard refuses a secret, an e-mail address, a private address or an internal host name.
- **Hosted models.** Rule 13 of `SECURITY.md` sends page text to a hosted group only when the task names one; the local tasks stay in the cluster, and the owner's hold on `claude-sonnet-5-5` stays.
- **Per-item and per-day budget.** #3066 parks a cost change until the baseline passes, and a research run is such a change.
- **Service request budget.** `src/devops_cli/roadmap/request_plan.py` lists each request, and `service.github_requests_per_hour` (default 500) bounds the Service (`docs/CONFIGURATION.md`).
- **Quality measure.** The ten-question measure below is the quality gate.

## Measure

The approving person records ten questions from the alternatives and refine comments of the last 30 days on #3877. No run is recorded at the date of this record, so this record writes no question ID, no hit rate and no cost per question; the measure stops with `premise_false` and the item returns to New. A run replaces this section with the question IDs, the hit rate and the cost per question against the SearXNG and DuckDuckGo baseline.

## Follow-up work

Each item names this record, `docs/adr/0028-a-research-agent-composes-open-tools-and-a-research-index.md`:

1. Add the `research` settings and the Qdrant collection, with the fields, expiry and deduplication of this record.
2. Add the `research` toolset to pydantic-ai: the chain, the Crawl4AI fetch, the ripgrep match and the Python `re` match.
3. Add the budget of #3066 and the Service request budget to the research run.
4. Run the ten-question measure, record the hit rate and the cost per question on #3877, and amend this record.

## More Information

- The item: #3877. The change: `openspec/changes/3877-investigate-a-web-research-agent-with/`.
- The records: `docs/adr/README.md`. The alternatives check: `src/devops_cli/roadmap/alternatives.py`.

## Status History

2026-11-17: Accepted by the owner, item #3877.

2026-11-18: Clarified (#6294): the index keeps one point for each `source_url`. The same hash updates `fetch_date` and `expiry`, and a new hash replaces the text and the `content_hash` of that point.
