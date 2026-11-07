## Purpose

Defines web search for the roadmap jobs: one entry point over a list of providers, the order and the failover of the providers, the guard on the query, the counter and the log line of each attempt, and the settings that choose the providers.

## ADDED Requirements

### Requirement: A search asks the providers in order and the first hit answers
`web_search` SHALL ask the providers of `search.providers` in order, SHALL skip a provider that is not configured or has no class, and SHALL return the hits of the first provider with at least one hit. It SHALL NOT ask a later provider after that. A hit SHALL have `url`, `title`, `snippet` and `provider`, and a search SHALL return at most `limit` hits.

#### Scenario: The first provider answers
- **WHEN** the providers are `firecrawl` and `duckduckgo`, and Firecrawl returns two hits
- **THEN** `web_search` returns the two hits with the provider `firecrawl`, and no request reaches DuckDuckGo

#### Scenario: A provider that is not configured
- **WHEN** the providers are `firecrawl` and `duckduckgo`, and no Firecrawl key is set
- **THEN** no request reaches Firecrawl, and the counter has no point with the backend `firecrawl`

#### Scenario: The default providers
- **WHEN** the settings have the default providers and a Firecrawl key
- **THEN** `searxng` is skipped, DuckDuckGo is asked first and Firecrawl second

### Requirement: A failed or empty provider passes the search on at once
A provider that fails (a timeout, a connect error, HTTP 401, 402, 403, 429, 5xx or another 4xx, or a reply that is not JSON or has no list) or returns no hit SHALL pass the search on to the next provider, with no retry and no wait. When no provider answered, `web_search` SHALL raise `SearchFailed`. When some provider answered with no hit and the rest failed, it SHALL return an empty list. The chain SHALL ask no provider after 60 s.

#### Scenario: A refusal
- **WHEN** Firecrawl answers HTTP 402, 429 or 500 and DuckDuckGo returns hits
- **THEN** the caller gets the hits of DuckDuckGo, and no wait ran

#### Scenario: A healthy empty reply
- **WHEN** Firecrawl answers with no hit and DuckDuckGo returns hits
- **THEN** the caller gets the hits of DuckDuckGo

#### Scenario: Every provider fails
- **WHEN** Firecrawl answers HTTP 402 and DuckDuckGo answers HTTP 500
- **THEN** `web_search` raises `SearchFailed`

#### Scenario: One answered empty and the rest failed
- **WHEN** Firecrawl answers with no hit and DuckDuckGo answers HTTP 500
- **THEN** `web_search` returns an empty list

#### Scenario: The deadline
- **WHEN** the first provider takes 61 s to fail
- **THEN** no later provider is asked, and `web_search` raises `SearchFailed`

### Requirement: The hits of an answer are unique and are web pages
`web_search` SHALL drop a hit whose URL has a scheme other than http or https, and SHALL keep one hit for URLs that differ only by a trailing slash. An answer with no hit left SHALL count as empty.

#### Scenario: A URL with another scheme
- **WHEN** a provider returns a hit with the URL `file:///etc/passwd`, a hit with a URL twice and a hit with an https URL
- **THEN** the caller gets the https hit and the first of the repeated URL

### Requirement: The guard refuses a query before any provider runs
`web_search` SHALL raise `SearchQueryRefused` and send no request for an empty query, a query over 400 characters or 50 words, a query that starts with `!` or `:`, and a query that holds a secret, an e-mail address, a private IP address or an internal host name. The message SHALL name the rule and SHALL NOT hold the query.

#### Scenario: Each refused query
- **WHEN** the query holds a token of a GitHub account, `dev@corp.test`, `192.168.49.2`, `storage.internal`, or starts with `!`
- **THEN** `SearchQueryRefused` is raised, no request is sent, and the counter has one point with the backend `none` and the result `refused`

#### Scenario: A version is no address
- **WHEN** the query is `macOS 10.15 release notes`
- **THEN** the query reaches the provider

### Requirement: Each attempt is counted
`web_search` SHALL add 1 to `devops_cli_web_searches_total` for each attempt of a provider, with the `backend` (the provider name) and the `result`: `ok`, `empty`, the HTTP status of a refused search, `degraded` for a reply that cannot be read, or `error` for no answer. A refused query SHALL count with the backend `none` and the result `refused`, and a search that no provider answered with the backend `none` and the result `exhausted`.

#### Scenario: A refusal counted
- **WHEN** Firecrawl answers HTTP 402 and DuckDuckGo returns hits
- **THEN** the counter has a point with the backend `firecrawl` and the result `402`, and a point with the backend `duckduckgo` and the result `ok`

#### Scenario: A reply that cannot be read
- **WHEN** Firecrawl answers with a body that is not JSON
- **THEN** the counter has a point with the backend `firecrawl` and the result `degraded`

### Requirement: A failed attempt is logged without the key or the query
A failed attempt SHALL log one warning that names the backend and the HTTP status or the error class, and SHALL NOT log the key or the query.

#### Scenario: A refusal logged
- **WHEN** Firecrawl answers HTTP 402 and DuckDuckGo times out
- **THEN** one warning says `A web search failed on firecrawl: HTTP 402.` and one says `A web search failed on duckduckgo: ConnectTimeout.`, and neither holds the key or the query

### Requirement: Each provider sends its request through the HTTP entry point
The requests of DuckDuckGo and Firecrawl SHALL go through the HTTP entry point at the public level. The DuckDuckGo request SHALL hold the query and no key, and the Firecrawl request SHALL hold the key of its own setting. Both SHALL send `search.language` as `Accept-Language`. The DuckDuckGo provider SHALL treat any answer other than HTTP 200 as a failure.

#### Scenario: The DuckDuckGo request
- **WHEN** DuckDuckGo is asked
- **THEN** the request holds the query and no `Authorization` header

#### Scenario: A bot challenge
- **WHEN** DuckDuckGo answers HTTP 202 with a page that has no hit
- **THEN** the counter has a point with the backend `duckduckgo` and the result `degraded`, and the search goes on

### Requirement: The settings name the providers and the language
The section `search` of the settings SHALL have `providers`, a list of `searxng`, `duckduckgo` and `firecrawl` with the default `searxng`, `duckduckgo`, `firecrawl`, and `language`, with the default `en`. An unknown provider name SHALL be a validation error. The variables SHALL be `DEVOPS_CLI_SEARCH_PROVIDERS` and `DEVOPS_CLI_SEARCH_LANGUAGE`. The text of `providers` SHALL say that `searxng` is skipped until its provider exists.

#### Scenario: An unknown provider
- **WHEN** the settings are built with the providers `duckduckgo` and `bing`
- **THEN** the settings raise a validation error that names `providers`
