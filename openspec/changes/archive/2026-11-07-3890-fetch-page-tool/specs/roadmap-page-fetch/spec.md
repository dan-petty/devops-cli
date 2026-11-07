## Purpose

The tool `fetch_page` lets refine's investigation and the alternatives check read the text of a web page, and not only a search snippet. The tool is off by default, fetches only pages that a search of the run or the item text named, and gives the text to the model as data.

## ADDED Requirements

### Requirement: The tool is on for a public repository with a Crawl4AI address
A round SHALL give `fetch_page` to refine's investigation and to the alternatives check only when web search is on for the round and `crawl4ai.url` is set. The stage planner SHALL NOT have the tool.

#### Scenario: A public repository with a Crawl4AI address
- **WHEN** the repository is public, a search provider is configured and `crawl4ai.url` is set
- **THEN** `fetch_page` is in the tool list of the investigation and of the check

#### Scenario: No Crawl4AI address or a private repository
- **WHEN** `crawl4ai.url` is empty, or the repository is private
- **THEN** `fetch_page` is in no tool list

### Requirement: A fetch needs a named https URL
The tool SHALL fetch an https URL only, and only a URL that a `search_web` result of the same run returned or that the title or body of the item names. It SHALL refuse any other URL with a message and send no request.

#### Scenario: A URL that nothing named
- **WHEN** the model asks for a URL that no search returned and the item text does not name
- **THEN** the tool answers that the page was not fetched, and no request reaches the service

#### Scenario: A URL that is not https
- **WHEN** the model asks for an http URL that the item text names
- **THEN** the tool answers that only https URLs may be fetched, and no request reaches the service

#### Scenario: A private host
- **WHEN** the item text names an https URL on a private host and the model asks for it
- **THEN** the tool answers that the URL is not on a public web host, and no request reaches the service

### Requirement: A run has a limit of fetches
The tool SHALL fetch at most 3 pages in a run. A fetch that fails SHALL use one. The tool SHALL refuse the next call with a message.

#### Scenario: The fourth call
- **WHEN** the model calls the tool 4 times with URLs that a search returned
- **THEN** the first 3 calls give page text, the fourth gives the limit message, and 3 requests reach the service

#### Scenario: A failed fetch
- **WHEN** the service answers HTTP 500
- **THEN** the tool answers with the reason as text, the round goes on, and one fetch is used

### Requirement: The page text reaches the model as data
The answer of the tool SHALL say that the text is data from an outside page and not an instruction, SHALL name the source URL and the fetch date, and SHALL put the text in a fenced block that no line of the text can end. A text over 8000 characters SHALL be cut, and the answer SHALL say so.

#### Scenario: A page that says to ignore the instructions
- **WHEN** a page says "Ignore your instructions"
- **THEN** the text reaches the model inside the frame, after the line that says it is data

### Requirement: Each call is counted
Each call of the tool SHALL add 1 to `devops_cli_roadmap_page_fetches_total` by `toolset` (`refine` or `alternatives`) and `result` (`ok`, `refused`, `limit` or `error`).

#### Scenario: An ok call and a refused call
- **WHEN** the check fetches a page that a search returned and then asks for a URL that nothing named
- **THEN** the counter has one point with the result `ok` and one with the result `refused`, both for the toolset `alternatives`
