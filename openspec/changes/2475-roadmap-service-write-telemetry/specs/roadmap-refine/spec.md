# Spec Delta

## ADDED Requirements

### Requirement: Refine writes at most two comments on one item in a day
A refine round SHALL leave an item alone, with no model call and no write, when refine wrote `CONST_ROADMAP_REFINE_MAX_COMMENTS_PER_ITEM` (2) comments that carry its marker on the item in the last 24 hours. The item SHALL wait on a person with the reason in the plan, and the round SHALL log one warning and add 1 to `devops_cli_roadmap_refine_comments_capped_total`. Comments older than 24 hours SHALL NOT count.

#### Scenario: Two refine comments within the day
- **WHEN** refine wrote two comments on an item 23 hours ago, another bot replied to each, and a round runs
- **THEN** the round makes no model call and writes no comment, the item waits on a person with the reason, and one warning and one count name the cap

#### Scenario: Two refine comments older than the day
- **WHEN** the two comments and the replies are 25 hours old
- **THEN** the round refines the item and writes its comment

### Requirement: Each Firecrawl search counts by its result
`firecrawl_search` SHALL add 1 to `devops_cli_firecrawl_searches_total` for each search, with the `result` `ok`, the HTTP status of a search that Firecrawl refused, or `error` for a search that got no answer or a reply with no web results. A failed search SHALL log one warning that names the status or the error class, and SHALL NOT log the key or the query.

#### Scenario: Firecrawl has no credits
- **WHEN** Firecrawl answers a search with HTTP 402
- **THEN** the counter has one point with the result `402`, and one warning says `Firecrawl answered with HTTP 402` and holds neither the key nor the query

#### Scenario: No answer
- **WHEN** the search times out at the connect
- **THEN** the counter has one point with the result `error`, and the warning names `ConnectTimeout`
