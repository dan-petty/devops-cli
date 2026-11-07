# ai-fetch-page Specification

## Purpose
The command `devops ai fetch-page` and the MCP tool `ai_fetch_page` read the text of one web page through the Crawl4AI service. The command takes the page URL only: the service address and the token come from the configuration and the credential store, so a model that calls the tool never writes a secret, a service address or a path.

## Requirements

### Requirement: The command prints the page text with its source
`devops ai fetch-page <url>` SHALL call `fetch_page_text` with the URL, and SHALL print the source URL, the time of the fetch, a line that says `truncated` when the text was cut, and then the page text. The source lines SHALL come before the text.

#### Scenario: A good fetch
- **WHEN** the service answers with the text of the page
- **THEN** the output holds the source URL and the text, and the exit code is 0

#### Scenario: A cut text
- **WHEN** the client cut the text at its cap
- **THEN** the output holds the line `truncated`

### Requirement: The command refuses with the reason
The command SHALL exit non-zero and print the reason when the page URL is refused, when `crawl4ai.url` is empty, when the token is empty or when the fetch fails. It SHALL send no request for a refused URL or an empty setting.

#### Scenario: A refused page URL
- **WHEN** the page URL names a private host or does not use http or https
- **THEN** the exit code is not 0, the output holds the reason, and the service gets no request

#### Scenario: The service address is not set
- **WHEN** `crawl4ai.url` is empty
- **THEN** the exit code is not 0 and the output names `crawl4ai.url`

#### Scenario: A failed fetch
- **WHEN** the service answers HTTP 503
- **THEN** the exit code is not 0 and the output holds the status

### Requirement: A dry run sends no request
`devops ai fetch-page --dry-run <url>` SHALL make no request. It SHALL check the page URL and the setting `crawl4ai.url`, and print the request that the real run sends, with the token as a placeholder. It SHALL NOT read or print the token.

#### Scenario: A dry run
- **WHEN** the command runs with `--dry-run` and the service is set
- **THEN** the HTTP fake gets no request, and the output holds `POST` and the `/md` address of the service and the placeholder for the token

### Requirement: The tool is read-only and takes no secret, service address or path
The exposure table SHALL hold the row for `ai fetch-page` as read-only, so the server publishes the tool `ai_fetch_page` in the `ai` domain with the read-only hint. The schema of the tool SHALL hold the properties `url` and `dry_run` and no other property. No job role of `_JOB_ROLE_TOOLS` SHALL hold the tool until a person approves the egress.

#### Scenario: The published tool
- **WHEN** an MCP client reads the schema of `ai_fetch_page`
- **THEN** the tool is read-only and its properties are `url` and `dry_run`

#### Scenario: The job roles
- **WHEN** the tool sets of the planning, implementation and review roles are listed
- **THEN** none of them holds `ai_fetch_page`
