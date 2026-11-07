# Proposal

## Why

The refine investigation and the alternatives check can find a page with `search_web`, but they cannot read it. They judge a claim such as "this flag exists" on a search snippet and not on the text of the page. The Crawl4AI client (`fetch_page_text`, #3887) is merged. This change gives both jobs a tool that reads a page through it (#3890). The owner approved the page-fetch egress for these two jobs only, with https URLs only, on 2026-11-07.

## What Changes

- A new module `src/devops_cli/roadmap/page_fetch.py` holds `PageFetch`, the state of the tool for one run, and `named_urls`, which reads the URLs that a text names.
- `InvestigationTools` (refine) and `AlternativesTools` get the tool `fetch_page(url)` next to `search_web`, when they hold a `PageFetch`. `StageTools` does not change: it overrides `tools()` and has no `search_web`.
- A round gives the tool only for a public repository with a configured search provider, and only when `crawl4ai.url` is set. `WebSearch` gets the field `fetch`.
- The tool fetches an https URL only. It refuses a URL that no `search_web` result of the same run returned and that the item text does not name, with a message and no request. It refuses the fetch after the third of a run. A fetch that fails is a tool answer, not an error of the round, and it uses one of the three.
- The answer frames the page text as data from an outside page, never an instruction, and names the source URL and the fetch date. The fence of the frame is longer than any run of backticks in the text. A page that was fetched joins the URLs that a source may cite.
- A new counter `devops_cli_roadmap_page_fetches_total{toolset,result}` counts each call: `ok`, `refused`, `limit` or `error`.
- The two task prompts and the request of each job name the tool. The request of refine holds `page_fetch`, and the request of the check holds `search_budget.page_fetches` when the tool is on.
- The change is observable in the tools of two jobs and in a metric, so it carries a spec delta for the new capability `roadmap-page-fetch`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-page-fetch`: The tool `fetch_page` of refine's investigation and of the alternatives check, its guards, its frame and its counter

## Impact

- Code: `src/devops_cli/roadmap/page_fetch.py` (new), `src/devops_cli/roadmap/refine/refine_investigation.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/ai/tasks/roadmap_refine_investigation.md`, `src/devops_cli/ai/tasks/roadmap_alternatives.md`
- Tests: `tests/roadmap/test_roadmap_page_fetch.py` (new), `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/refine/test_roadmap_refine.py`, `tests/roadmap/refine/test_roadmap_refine_investigation.py`
- Documents: `docs/roadmap/refine.md`, `docs/roadmap/alternatives.md`, `k8s/README.md`, `docs/TELEMETRY.md` (generated)
- Cluster: none. The live ConfigMap and the cluster are not changed. The tool stays off until a person sets `crawl4ai.url` there.
- Dependencies: none

## Feasibility

- The client exists on `main`: `fetch_page_text` in `src/devops_cli/ai/page_text.py` (merged with #3943, read on 2026-11-07). It checks the scheme and the host of a URL before any request, dials the Crawl4AI service only, follows no redirect, cuts the text at `max_chars` and counts each fetch in `devops_cli_crawl4ai_fetches_total`.
- The setting `crawl4ai.url` exists in `Crawl4AIConfig` and has no default, so the tool is off with the default settings.
- `search_web` has the conventions that the tool follows: `cited_web_search` keeps the URLs of the hits, and `web_search_of` decides whether a round has web search.
- `StageTools` extends `InvestigationTools` and overrides `tools()`. A test of the tool list of a plan run shows that it has no `fetch_page`.
- The egress of the tool is the approved one: the page is read by the Crawl4AI service, and the job dials only the service, at the private level. The owner approved the page-fetch egress for refine and alternatives, https only, on 2026-11-07.
- `fetch_page_text` accepts http and https, so the tool checks the https rule itself, before it calls the client.

## Existing Tool Considered

The Crawl4AI client of #3887 reads the page, and the project already ships it. The conventions of `web_search.py` are followed, and no agent framework is added (#3877 decides the research agent). For the URLs that a text names, the change uses `CONST_URL_CANDIDATE_RE` of the sanitizer. For the fence of the frame it uses `code_fence`. For the checks of the host it uses the client, which uses `is_loopback_or_private_host`. The code that the change adds is about 120 lines in one module, and the cost is about 30k tokens to build and keep, and 2 hours. The change deletes no internal code.

## Dependencies

None. #3887 and #3925 are merged.
