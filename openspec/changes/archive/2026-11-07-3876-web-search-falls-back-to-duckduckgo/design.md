# Design

## Decisions

- **Put `web_search` and `duckduckgo_search` in `src/devops_cli/ai/common_tools.py`.**: The module already holds `firecrawl_search`, its counter and its log line, and `cited_web_search` is its only caller.
- **Keep `firecrawl_search` as the Firecrawl backend and let `web_search` call it.**: Its counter `devops_cli_firecrawl_searches_total` keeps its meaning, and the alert `RoadmapServiceFirecrawlRefused` still counts each refusal.
- **Fall back on `httpx2.HTTPError` and `ValueError`.**: These are the failures that `firecrawl_search` raises for a refusal (HTTP 402, 429, 5xx), a timeout, a lost connection and a reply with no `data.web` list. A search that returns an empty list is an answer, and runs no fallback.
- **Count the fallback in a new counter `devops_cli_web_search_fallbacks_total` with `backend` and `result`.**: The name of the old counter says Firecrawl, so it cannot count another backend without a change of meaning. The `backend` attribute lets a later backend (SearXNG) use the same counter.
- **Raise the failure of DuckDuckGo when both backends fail.**: It is an `httpx2.HTTPError` or a `ValueError`, the two classes that `cited_web_search` already handles, so the job goes on as it does after a Firecrawl failure.
- **Send the request with `http_client(level=EgressLevel.PUBLIC)` and use the engine of `ddgs` for the payload and the parse.**: The HTTP client of `ddgs` is `primp` and takes no transport. The project sends every request through `devops_cli.http.entry`.
- **Treat any answer other than HTTP 200 as an error.**: DuckDuckGo answers a client that it takes for a bot with HTTP 202 and a page with no result. Without the check, the parse returns an empty list and the job reads it as a search with no result.
- **Import `ddgs` inside `duckduckgo_search`.**: The import loads `lxml` and all engines and takes about 0.4 s. Only a failed Firecrawl search pays it.
- **Log the fallback at warning level, once per search, with the HTTP status or the error class.**: This is the form of the Firecrawl failure line, and it holds neither the key nor the query.

## Rejected alternatives

- **Call `DDGS().text(...)` or the pydantic-ai `duckduckgo_search_tool`.**: `DDGS` builds a `primp.Client` and takes no transport, so the request skips the egress check of the project. With the default backend `auto` it also asks other search engines. A test with the shared HTTP fake could not see the request.
- **Write a parser of the DuckDuckGo page in the project.**: The issue forbids a home-grown scraper, and `ddgs` keeps the XPath rules current when DuckDuckGo changes its page.
- **Rename `devops_cli_firecrawl_searches_total` to a neutral name.**: The alert `RoadmapServiceFirecrawlRefused`, the dashboard and the alert `RoadmapServiceAlternativesNotSearching` read it, and the issue asks that it keeps its meaning.
- **Add a `backend` label to `devops_cli_firecrawl_searches_total`.**: A series of that name would count DuckDuckGo searches, and the meaning of the name would change.
- **Search DuckDuckGo when no Firecrawl key is set.**: The jobs turn the web search off with no key, and a person has not decided that the web search may run with no key. It is a separate item.
