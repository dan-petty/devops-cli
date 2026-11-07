# crawl4ai-page-text Specification

## Purpose
The text of a web page from the Crawl4AI service, as a client that a model-chosen page URL can reach safely: the page URL is checked before any request, the reply and the text have caps, the text is untrusted data, and each fetch is counted without the token or the page URL in a log.

## Requirements

### Requirement: A fetch posts the page to the service with the bearer token
`fetch_page_text` SHALL send one `POST {crawl4ai.url}/md` with the JSON body `{"url": <page URL>, "f": "fit"}` and the header `Authorization: Bearer <crawl4ai.api_token>`, and SHALL return a `PageText` with the requested URL as `source_url`, the `markdown` of the reply as `text`, the time of the fetch as `fetched_at` and `truncated`. It SHALL follow no redirect.

#### Scenario: A good call
- **WHEN** the service answers the request with the reply shape of Crawl4AI v0.9.5
- **THEN** the request holds the bearer header and the body, and the result holds the Markdown of the reply, the requested URL and `truncated` false

#### Scenario: The reply names another URL
- **WHEN** the reply holds a `url` that differs from the requested page URL
- **THEN** `source_url` is the requested page URL

#### Scenario: The service redirects
- **WHEN** the service answers with a redirect
- **THEN** the client sends no second request and raises `PageTextError` with the status of the redirect

### Requirement: A page URL is checked before any request
`fetch_page_text` SHALL raise `InvalidURLError` for a page URL whose scheme is not http or https, and `SSRFBlockedError` for a host that `is_loopback_or_private_host` refuses, and SHALL send no request in either case. A refusal SHALL NOT count in `devops_cli_crawl4ai_fetches_total`.

#### Scenario: A scheme that is not http or https
- **WHEN** the page URL is `file:///etc/passwd`
- **THEN** `InvalidURLError` is raised and no request is sent

#### Scenario: A private, loopback or metadata host
- **WHEN** the page URL names `192.0.2.5`, `127.0.0.1`, `169.254.169.254`, `metadata.google.internal` or `kubernetes.default.svc`
- **THEN** `SSRFBlockedError` is raised and no request is sent

### Requirement: The reply and the text have caps
The client SHALL refuse a reply of more than `DEFAULT_CRAWL4AI_MAX_REPLY_BYTES` bytes with `PageTextError`. It SHALL cut the text at `max_chars` characters and set `truncated` true when it cut.

#### Scenario: Text over the cap
- **WHEN** the reply holds 10 characters and `max_chars` is 4
- **THEN** `text` holds the first 4 characters and `truncated` is true

#### Scenario: Text at the cap
- **WHEN** the reply holds 10 characters and `max_chars` is 10
- **THEN** `text` holds all 10 characters and `truncated` is false

#### Scenario: A reply over the byte cap
- **WHEN** the reply holds more than `DEFAULT_CRAWL4AI_MAX_REPLY_BYTES` bytes
- **THEN** `PageTextError` is raised and the fetch counts `error`

### Requirement: Each fetch counts by its result
A fetch that reaches the service SHALL add 1 to `devops_cli_crawl4ai_fetches_total` with `result` set to `ok`, to the HTTP status of a reply that is not a success, or to `error` for no answer or a reply that is not page text. A failed fetch SHALL log one warning that names the status or the class of the failure and holds neither the token nor the page URL, and SHALL raise `PageTextError`.

#### Scenario: A refused fetch
- **WHEN** the service answers HTTP 401, 403, 429 or 504
- **THEN** the counter has one point with that status as `result`, `PageTextError` carries the status, and the log line and the error hold no token and no page query

#### Scenario: No page text
- **WHEN** the service times out, or its reply is not JSON, or has no `markdown` text, or has `success` false
- **THEN** the counter has one point with `result` `error`

### Requirement: A missing setting or credential is named
`fetch_page_text` SHALL raise `ConfigurationError` that names `crawl4ai.url` when the setting is empty, and one that names `crawl4ai.api_token` when the credential is empty, and SHALL send no request.

#### Scenario: The service address is not set
- **WHEN** `crawl4ai.url` is empty
- **THEN** `ConfigurationError` is raised with the key `crawl4ai.url` and no request is sent
