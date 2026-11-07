## MODIFIED Requirements

### Requirement: Refine investigates a question that has no verified source
When a validated proposal has a fact or a decision with no verified source, or a body key question that no answer names, refine SHALL run one investigation for the item with read-only tools on the pinned commit, and with web search for a public repository with at least one configured search provider. Refine SHALL validate the proposal that the investigation returns as it validates the first. When nothing is open, refine SHALL make no investigation request.

#### Scenario: A fact that a file read settles
- **WHEN** the first proposal answers "Where is the sample function?" as a fact with no source, and the investigation reads `src/sample.py` and answers with the source `src/sample.py:1`
- **THEN** the item has no open question, and refine sets it to Ready

#### Scenario: A fact that a web search settles
- **WHEN** the repository is public, a search provider is configured, the investigation's web search returns `https://example.com/gitleaks`, and the investigation answers the fact with that URL as its source
- **THEN** the item has no open question, and refine sets it to Ready

#### Scenario: A proposal with nothing open
- **WHEN** the first proposal has no open question
- **THEN** refine makes one model request for the item and runs no investigation

## REMOVED Requirements

### Requirement: The plan says when web search is off
**Reason**: The reason is no search provider, no longer a missing Firecrawl key, and its scenario names the key.
**Migration**: The requirement "The plan says when web search is off for want of a provider" holds the rule.

### Requirement: Each Firecrawl search counts by its result
**Reason**: The counter `devops_cli_firecrawl_searches_total` is replaced by `devops_cli_web_searches_total` for all providers.
**Migration**: The requirement "Each attempt is counted and a failed attempt is logged" of the capability `web-search` holds the rule.

### Requirement: A failed Firecrawl search falls back to DuckDuckGo
**Reason**: The chain of providers replaces the fallback of one backend after another.
**Migration**: The requirements "A search asks the providers in order and the first hit answers" and "A failed or empty provider passes the search on at once" of the capability `web-search` hold the rule.

### Requirement: The fallback is public, private to the query and counted
**Reason**: The counter `devops_cli_web_search_fallbacks_total` is replaced by `devops_cli_web_searches_total`.
**Migration**: The requirements "Each provider sends its request through the HTTP entry point", "Each attempt is counted" and "A failed attempt is logged without the key or the query" of the capability `web-search` hold the rule.

## ADDED Requirements

### Requirement: The plan says when web search is off for want of a provider
When refine had no web search in a round, the plan SHALL say so once, with the reason: the repository is private, its visibility could not be read, or no search provider is configured.

#### Scenario: No search provider
- **WHEN** refine plans a round on a public repository whose providers are all unconfigured
- **THEN** the report says that web search is off because no search provider is configured

#### Scenario: The keyless provider
- **WHEN** refine plans a round on a public repository with the default providers and no Firecrawl key
- **THEN** web search is on
