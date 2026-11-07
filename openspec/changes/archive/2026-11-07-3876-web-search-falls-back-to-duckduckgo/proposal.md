# Proposal

## Why

The web search of the roadmap jobs has one backend: the hosted Firecrawl API. When Firecrawl refuses a search, the search returns nothing. On 2026-11-06 the Service logged 7 searches in 24 hours that failed with `Firecrawl answered with HTTP 402`, because the credit of the account was used up. The alternatives check and the refine investigation then ran without web results, and the check could not tell a missing tool from a failed search (#3876).

## What Changes

- `src/devops_cli/ai/common_tools.py` gains `web_search`. It calls `firecrawl_search`. When that call raises `httpx2.HTTPError` or `ValueError`, it logs one line with the reason and calls `duckduckgo_search`. A search that Firecrawl answered runs no fallback.
- `duckduckgo_search` builds the request and reads the page with the `DuckDuckGo` engine of the `ddgs` package, and sends the request through `http_client(level=EgressLevel.PUBLIC)`. It returns each result as `url`, `title` and `description`, the form of a Firecrawl result.
- A new counter `devops_cli_web_search_fallbacks_total` has the attributes `backend` (`duckduckgo`) and `result` (`ok` or `error`). `devops_cli_firecrawl_searches_total` keeps its meaning.
- When both backends fail, `web_search` raises as a Firecrawl failure does, so `cited_web_search` answers the failure as text and the job goes on.
- `cited_web_search` in `src/devops_cli/roadmap/refine_investigation.py` calls `web_search`. The alternatives tool uses `cited_web_search`, so both jobs get the fallback.
- `ddgs==9.16.1` joins `pyproject.toml` and `uv.lock`.
- `docs/TELEMETRY.md`, `k8s/README.md` and `docs/roadmap/alternatives.md` name the fallback. The text of the alert `RoadmapServiceFirecrawlRefused` says that the search falls back.
- The change is observable by a job and by the metrics, so the `roadmap-refine` capability gains one requirement.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-refine`: A failed Firecrawl search falls back to DuckDuckGo

## Impact

- Code: `src/devops_cli/ai/common_tools.py`, `src/devops_cli/roadmap/refine_investigation.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`
- Tests: `tests/ai/test_common_tools.py`, `tests/http/test_http_egress.py`, `tests/roadmap/test_roadmap_dry_runs.py`
- Documents: `docs/TELEMETRY.md`, `k8s/README.md`, `docs/roadmap/alternatives.md`
- Manifests: the description of the alert `RoadmapServiceFirecrawlRefused` in `k8s/monitoring/prometheus-values.yaml`
- Dependencies: `ddgs` 9.16.1, with `primp` 2.0.1 and `lxml` 6.1.3 (new in `uv.lock`)

## Feasibility

- `ddgs` 9.16.1 is on PyPI with license MIT, and was published on 2026-10-23, 15 days before this change. The project is active: 17 releases since 2025-10. The new transitive packages are `primp` 2.0.1 (MIT, 2026-09-13) and `lxml` 6.1.3 (2026-09-02). Both ship `cp314` wheels for manylinux and musllinux, so the `python:3.14-slim-trixie` stage of the `Dockerfile` installs them with `uv sync --locked` and no compiler. `uv lock` resolved the three packages, and `uv sync --locked` installed them.
- The `pydantic-ai` DuckDuckGo tool (`pydantic_ai.common_tools.duckduckgo`) only wraps `ddgs.DDGS().text`. It takes no HTTP client. `DDGS` sends its requests with `primp.Client`, and the constructor takes only `proxy`, `timeout` and `verify`. So neither the tool nor `DDGS` can send the request through the HTTP entry point, and a request of `primp` would skip the egress check of `devops_cli.http.client` (SECURITY.md rule 2).
- The engine class has no such limit. In the source of `ddgs` 9.16.1, `ddgs/engines/duckduckgo.py` splits the work into `build_payload` (a dict, no request), a request, and `extract_results` and `post_extract_results` (parse the HTML, no request). This change calls those parts and sends the request with `http_client`. The engine instance builds a `primp.Client` in its constructor and sends nothing with it.
- Command output of 2026-11-07 on this host: `DDGS(timeout=15).text("pydantic ai agent framework", max_results=3)` returned 3 results, and a plain POST of `q=ruff python linter` to `https://html.duckduckgo.com/html/` with the User-Agent `devops-cli/<version>` returned HTTP 200 with `result__body` blocks that the engine parses. So the entry point does not need the browser impersonation of `primp`. DuckDuckGo can still answer a client that it takes for a bot with HTTP 202 and a page with no result. `duckduckgo_search` treats any answer other than HTTP 200 as an error, so the failure is counted and the search ends as a Firecrawl failure does.
- Egress: the policy `devops-default-perimeter` in `k8s/devops/networkpolicy.yaml` admits TCP 443 to public addresses (rule 4, with the private, shared, link-local, metadata and benchmark ranges excluded). `html.duckduckgo.com` is public HTTPS, so no manifest changes. The client runs at the `PUBLIC` level, so a private or metadata answer of DNS is refused at the connect. `tests/http/test_http_egress.py` holds the new caller `duckduckgo` at that level.
- Query content: the callers send a short search query that the model writes (`search_web` in `refine_investigation.py` and `alternatives.py`). The query goes in the body of the DuckDuckGo request and nowhere else. The request holds no key, and the log line of the fallback holds the reason only.
- Not done here: a fallback with no Firecrawl key. The jobs turn the web search off when no key is set, and the issue asks for a fallback after a failed search. A search with no key is a separate decision.

## Existing Tool Considered

The `ddgs` package (MIT, maintained, 9.16.1) covers the search and the parse of the DuckDuckGo page, as the issue asks. The change builds no scraper: it calls `build_payload`, `extract_results` and `post_extract_results` of the `ddgs` engine, and adds only the request through the HTTP entry point, about 20 lines. The pydantic-ai tool does not fit, because it hides the HTTP client (see Feasibility). SearXNG is a second option for a later item. The change deletes no code. The written cost is about 15k tokens to build and keep, and 1 hour.

## Dependencies

None.
