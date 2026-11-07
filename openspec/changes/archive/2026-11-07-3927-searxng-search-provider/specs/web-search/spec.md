## ADDED Requirements

### Requirement: The SearXNG provider is configured by its address
The provider `searxng` SHALL be configured when `search.searxng_url` is set, and SHALL be skipped without it. A direct call without the setting SHALL raise `ConfigurationError` that names `search.searxng_url`.

#### Scenario: No address
- **WHEN** `search.searxng_url` is not set
- **THEN** no request reaches SearXNG and the counter has no point with the backend `searxng`

### Requirement: The SearXNG provider searches with a JSON request
The provider SHALL send `GET <address>/search` with `q`, `format=json`, `language` (the value of `search.language`), `categories` and `pageno=1`. It SHALL map each item of `results` that has a `url` to a hit with `url`, `title`, `content` as the snippet, and the provider `searxng`.

#### Scenario: A good reply
- **WHEN** the providers are `searxng` and the service answers with three results
- **THEN** `web_search` returns three hits with the provider `searxng`, and the counter has a point with the backend `searxng` and the result `ok`

#### Scenario: The request
- **WHEN** a search runs for a query with `search.language` set to `de`
- **THEN** one `GET` reaches `/search` with the parameters `q`, `format=json`, `language=de`, `categories` and `pageno=1`

### Requirement: The SearXNG client dials by the configured egress level
The provider SHALL send its request through the HTTP entry point at the configured level: loopback, or private when `ai.allow_private_network` is set.

#### Scenario: A loopback address
- **WHEN** `search.searxng_url` is a loopback address and `ai.allow_private_network` is off
- **THEN** the search reaches the service

#### Scenario: A cluster address
- **WHEN** `search.searxng_url` is a cluster Service address that resolves to a private address and `ai.allow_private_network` is off
- **THEN** a direct call raises `SSRFBlockedError` and no request is sent, and with the setting on the search reaches the service

### Requirement: The SearXNG client follows no redirect and reads a capped reply
The provider SHALL follow no redirect and SHALL read at most 1 MiB of a reply. A reply with a status other than 200, a redirect included, SHALL count with the status as the result and SHALL pass the search on.

#### Scenario: A status other than 200
- **WHEN** the service answers HTTP 403, 429 or 503
- **THEN** the counter has a point with the backend `searxng` and that status as the result, and the next provider is asked

#### Scenario: A redirect
- **WHEN** the service answers HTTP 302
- **THEN** one request was sent, and the counter has a point with the backend `searxng` and the result `302`

### Requirement: A SearXNG reply that cannot answer passes the search on
A reply over the byte cap, a reply that is not a JSON object with a `results` list, and a reply with no result and a non-empty `unresponsive_engines` SHALL count as `degraded`. A reply with no result and an empty `unresponsive_engines` SHALL count as `empty`. An address that the egress check refuses SHALL count as `refused`. Each SHALL pass the search on.

#### Scenario: Engines that did not answer
- **WHEN** the service answers with an empty `results` and a non-empty `unresponsive_engines`
- **THEN** the counter has a point with the backend `searxng` and the result `degraded`

#### Scenario: No result
- **WHEN** the service answers with an empty `results` and an empty `unresponsive_engines`
- **THEN** the counter has a point with the backend `searxng` and the result `empty`

#### Scenario: A refused address
- **WHEN** the egress check refuses the address of the service
- **THEN** the counter has a point with the backend `searxng` and the result `refused`, and the next provider is asked

### Requirement: The dry run lists the method of the first provider
The dry run of `devops roadmap alternatives` SHALL list the method and the URL of the request of the first configured provider.

#### Scenario: SearXNG is first
- **WHEN** `searxng` is the first configured provider
- **THEN** the dry run lists `GET` with the search endpoint of the service, and no request to DuckDuckGo

## MODIFIED Requirements

### Requirement: The settings name the providers and the language
The section `search` of the settings SHALL have `providers`, a list of `searxng`, `duckduckgo` and `firecrawl` with the default `searxng`, `duckduckgo`, `firecrawl`, `language`, with the default `en`, and `searxng_url`, with no default. An unknown provider name SHALL be a validation error. The variables SHALL be `DEVOPS_CLI_SEARCH_PROVIDERS`, `DEVOPS_CLI_SEARCH_LANGUAGE` and `DEVOPS_CLI_SEARCH_SEARXNG_URL`. The text of `providers` SHALL say that `searxng` is skipped without `search.searxng_url`.

#### Scenario: An unknown provider
- **WHEN** the settings are built with the providers `duckduckgo` and `bing`
- **THEN** the settings raise a validation error that names `providers`

#### Scenario: The address has no default
- **WHEN** the settings are built with no value for `search.searxng_url`
- **THEN** `search.searxng_url` is not set
