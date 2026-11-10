# Audit: places where devops-cli reads the web (#2432)

The audit ran at the base commit of this change. Credit prices are those of the Firecrawl price list: 1 credit for a scrape or a crawled page, 1 credit for a map call, 2 credits for 10 search results, and 4 more credits for a page with structured extraction.

## Corrections to the issue body

- `ingest_remote_docs` opens its client with `http_client(EgressLevel.PUBLIC, timeout=httpx2.Timeout(30.0))` from `devops_cli.http.entry` (`src/devops_cli/ai/library/docs_ingester.py:260`). It does not bypass the egress factory.
- Firecrawl is the last provider of web search (`docs/CONFIGURATION.md`, setting `search.providers`: `searxng`, `duckduckgo`, `firecrawl`). The cluster also runs Crawl4AI, and `fetch_page_text` reads a page through it (`src/devops_cli/ai/page_text.py:68`, `k8s/README.md`, section Crawl4AI).
- `src/devops_cli/ai/research/crawler.py` reads no web page. It follows edges of a repository only.
- The knowledge base has 59 entries with a `sources:` line. No code reads those URLs.

## Census

Each line is a probe and its result at the base commit.

| Probe | Result |
| :--- | :--- |
| `git grep -nE "class .*HTMLParser\|html\.parser\|BeautifulSoup\|markdownify\|trafilatura" -- src` | `docs_ingester.py:42` (`_HTMLContentExtractor`), `ci/fail_to_pass.py:146` (`_JUnitHTMLParser`) |
| `git grep -nE "EgressLevel\.PUBLIC" -- src` | 20 lines. Each is a client of a fixed public API or registry, a policy table or a check of an address, except `ai/library/docs_ingester.py:260` and `ai/web_search.py:143,173` |
| `git grep -n "/md" -- src/devops_cli/ai/page_text.py` | One request, `POST {crawl4ai.url}/md` |
| `git grep -lE "^sources:" -- src/devops_cli/ai/knowledge_base` | 59 files |

## Decisions

| Place | Today | Crawl4AI | Firecrawl | Cost and egress | Private data | Decision and reason |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `ai/library/docs_ingester.py:260`, `ingest_remote_docs`, with `_HTMLContentExtractor` at `:42` (`devops ai ingest docs`) | Walks child links from a URL that a person gives, up to `--max-pages` (default 10), and turns HTML into Markdown chunks. Static HTML only. | Renders JS and gives Markdown for one page. Gives no link list from `/md`. Unreachable from a workstation: only the pods of `roadmap-service` may call it. | `/v2/crawl` covers the walk and the Markdown, and renders JS. Needs a key and a hosted call. | Firecrawl: up to 10 credits for each run. Own code: 0. The client dials public addresses only. | None by design: a person names a public docs URL, and the client refuses a non-public address. | **Keep.** The census holds no page that the parser fails on. Crawl4AI cannot serve the caller, and Firecrawl adds a key and a credit cost for a command with no failure to fix. Adopt Firecrawl `/v2/crawl` when an item shows a page that the parser cannot read. |
| `ai/page_text.py:68`, `fetch_page_text` | Reads a page through Crawl4AI `POST /md`. | Is the tool. | `/v2/scrape` serves the same need. | Crawl4AI: 0 credits, data stays in the network. Firecrawl: 1 credit for each page. | A model chooses the URL, and the tool takes only a URL of a search result or of the item text. | **Keep.** The open tool already serves this place at no credit cost. |
| `roadmap/page_fetch.py`, tool `fetch_page` of refine and of the alternatives check | Calls `fetch_page_text` with a cap of fetches for each run. | Is the tool, through `fetch_page_text`. | Same as the row above. | Same as the row above. | Same as the row above. | **Keep.** It is a user of the row above. |
| `ai/ai_plans.py:867`, `plan_ai_fetch_page` | Plans the one `POST /md` request of `devops ai fetch-page` for `--dry-run`. | Is the tool. | None needed. | No request is sent. | None. | **Keep.** It describes the Crawl4AI request. |
| `ai/web_search.py:114,160,201`, `DuckDuckGoProvider`, `FirecrawlProvider`, `SearxngProvider` | Search through `searxng`, then `duckduckgo`, then `firecrawl`. | Gives no search. | `/v2/search` is already adopted as the last provider. | Firecrawl: 2 credits for 10 results, only when the first two providers fail. | A guard (`_guard`) refuses a query that holds a private part. | **Keep.** Firecrawl is already adopted for search, in the order the owner chose. |
| `ai/research/crawler.py` | Follows imports, Markdown links and git co-changes of a repository. | Not applicable: it reads no web page. | Not applicable. | None. | The repository can be private, so no hosted tool applies. | **Keep.** It is not a web reader. |
| `ai/knowledge_base/**` (`sources:` lines) | Metadata. No code fetches the URLs. | Could read each source. | `/v2/scrape` could read each source. | 59 pages for a full check. | None. | **Keep.** No feature exists, so the audit has no place to decide. A drift check is a new issue. |
| `ci/fail_to_pass.py:146`, `_JUnitHTMLParser` | Reads a local JUnit report. | Not applicable. | Not applicable. | None. | Local files. | **Keep.** It reads no web page. |
| `roadmap/alternatives.py:256`, `survey/dependencies.py:165`, `roadmap/run.py:692`, `argo/image_pins.py:101`, `commands/k8s/image_pins.py:60`, `security/semgrep_registry.py:172`, `http/public_api.py:39` | Read JSON, a registry manifest or a rule archive from a fixed public API. | Not applicable: they read no page. | `/v2/scrape` gives page text, not an API reply. | None. | None. | **Keep.** A fixed API with a typed reply needs no scraper. |
| `ai/client/**` | Calls of the model providers. | Not applicable. | Not applicable. | Not applicable. | A prompt can hold private data, so no hosted scraper applies. | **Keep.** It is not a web reader. |
| Firecrawl `/v2/map` and `/v2/extract` | No place needs a URL map or a structured extraction. | Not applicable. | Not applicable. | Map: 1 credit for each call. Extract: 5 credits for each page. | Not applicable. | **Keep.** No place to adopt. |

## Result

No place adopts Firecrawl, so no item is filed. The audit changes no file under `src/`.
