# Proposal: #2432

## Why

Issue #2432 asks which web-reading features of devops-cli a hosted Firecrawl API serves better than the code that they use today. The issue body was written before Crawl4AI joined the cluster (#3887), so two claims of the body are false at `main`:

- `ingest_remote_docs` does not bypass the egress factory. It opens `http_client(EgressLevel.PUBLIC, timeout=httpx2.Timeout(30.0))` (`src/devops_cli/ai/library/docs_ingester.py:260`).
- Firecrawl is not the only tool for page text or search. Web search asks `searxng`, `duckduckgo` and `firecrawl` in that order (`docs/CONFIGURATION.md`, setting `search.providers`), and the tool `fetch_page` reads a page through the Crawl4AI service (`k8s/README.md`, section Crawl4AI).

The audit compares both tools for each place, and records one decision for each place in [audit.md](audit.md). Closes #2432.

## What Changes

- Add `audit.md` to this change folder. It lists each place under `src/` that searches the web, fetches a web page or turns web HTML into text, with file and line, current behavior, the covering tool, the credit cost, whether private data is involved, and the decision with its reason.
- No file under `src/` changes. No place adopts Firecrawl, so the audit files no follow-up item.

The change has no spec delta (`skip_specs: true`): it alters no command, option, message, manifest or service behavior.

## Capabilities

None. No capability is added or modified.

## Impact

None for a user or a service. The audit record is the only new file.

## Feasibility

The audit reads the code at `main` and the upstream price list. Each probe line of `audit.md` (section Census) ran at the commit that this change is based on:

- `git grep -lE "EgressLevel\.PUBLIC|HTMLParser|text/html|\bscrape|\bcrawl" -- src/` listed the candidate files. Each candidate was read.
- `git grep -nE "class .*HTMLParser|html\.parser|BeautifulSoup|markdownify|trafilatura" -- src` found two `HTMLParser` subclasses: `_HTMLContentExtractor` (web HTML) and `_JUnitHTMLParser` (local JUnit report).
- `k8s/README.md` (section Crawl4AI) states that only the pods of `roadmap-service` may call Crawl4AI, and that a Job pod cannot.
- The Firecrawl price list gives 1 credit for a scrape or a crawled page, 1 credit for a map call and 2 credits for 10 search results. A structured extraction adds 4 credits for a page. The free tier gives 1,000 credits a month.

The premise (some place reads the web with its own code) holds for one place, `ingest_remote_docs`. The premise that it bypasses the egress factory is false and the audit corrects it.

The change fits one pull request.

## Existing Tool Considered

The tools are Crawl4AI (open source, Apache-2.0, deployed in the cluster, no credit cost, data stays in the network) and Firecrawl (hosted API, credit cost, the Python SDK bypasses the egress factory, so a use calls the REST API through `devops_cli.http.entry.http_client`). The audit builds no code. Its cost is about 30,000 tokens and 30 minutes to read the places and write the record. The change deletes no internal code.
