## ADDED Requirements

### Requirement: A failed Firecrawl search falls back to DuckDuckGo
`web_search` SHALL search DuckDuckGo when the Firecrawl search raises an `httpx2.HTTPError` or a `ValueError`, and SHALL return the results in the form of Firecrawl results, each with `url`, `title` and `description`. It SHALL NOT search DuckDuckGo after a search that Firecrawl answered, also one with no result. When DuckDuckGo fails too, it SHALL raise an `httpx2.HTTPError` or a `ValueError`, so `cited_web_search` answers `The search failed` as text and the job goes on.

#### Scenario: Firecrawl has no credits
- **WHEN** Firecrawl answers a search with HTTP 402 and DuckDuckGo answers with a page of results
- **THEN** the caller gets the results with `url`, `title` and `description`

#### Scenario: Firecrawl answers
- **WHEN** Firecrawl answers a search with results, or with no result
- **THEN** no request reaches DuckDuckGo

#### Scenario: Both backends fail
- **WHEN** Firecrawl answers HTTP 402 and DuckDuckGo answers HTTP 500, or HTTP 202 for a bot challenge
- **THEN** `web_search` raises an `httpx2.HTTPError` or a `ValueError`

#### Scenario: The fallback keeps the limit
- **WHEN** Firecrawl fails, DuckDuckGo returns 3 results and the limit is 2
- **THEN** the caller gets the first 2 results

### Requirement: The fallback is public, private to the query and counted
The DuckDuckGo request SHALL go through the HTTP entry point at the public level, and SHALL hold the query and no key. The fallback SHALL log one line with the HTTP status or the error class, and SHALL NOT log the key or the query. It SHALL add 1 to `devops_cli_web_search_fallbacks_total` with the `backend` `duckduckgo` and the `result` `ok` or `error`.

#### Scenario: A fallback that answers
- **WHEN** Firecrawl answers a search with HTTP 402 and DuckDuckGo answers with a page of results
- **THEN** the DuckDuckGo request holds the query and no `Authorization` header, one line says `A web search fell back to DuckDuckGo: Firecrawl answered with HTTP 402.`, and the fallback counter has one point with the result `ok`

#### Scenario: A fallback that fails
- **WHEN** Firecrawl and DuckDuckGo both answer with an error
- **THEN** the fallback counter has one point with the result `error`
