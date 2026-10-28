# Spec Delta

## ADDED Requirements

### Requirement: Refine writes at most two comments on one item in a day
Without `--item`, a refine round SHALL leave an item alone, with no model call and no comment, when refine wrote `CONST_ROADMAP_REFINE_MAX_COMMENTS_PER_ITEM` (2) comments that carry its marker on the item in the last 24 hours. The item SHALL wait on a person with the reason in the plan, and SHALL take no place under the round's limit. Comments older than 24 hours SHALL NOT count.

#### Scenario: Two refine comments within the day
- **WHEN** refine wrote two comments on an item 23 hours ago, another bot replied to each, and a round runs with `--confirm`
- **THEN** the round makes no model call and writes no comment, the item waits on a person with the reason, and one warning and one count name the cap

#### Scenario: Two refine comments older than the day
- **WHEN** the two comments and the replies are 25 hours old
- **THEN** the round refines the item and writes its comment

#### Scenario: Items at the cap fill no place
- **WHEN** another bot replied to two refine comments on each of three P0 items in the last hour, a P1 item is New, and a round runs with a limit of 3
- **THEN** the round refines the P1 item with one model call, and the three P0 items wait on a person

### Requirement: Each comment that the cap stops counts once
The cap stops the comment that would answer the item's newest comment. For each such comment that no earlier round recorded, `--confirm` SHALL record the comment's creation time in the item's job record as `refine.capped_after`, log one warning and add 1 to `devops_cli_roadmap_refine_comments_capped_total`. A round that finds the recorded comment still the newest SHALL write, log and count nothing for the item.

#### Scenario: A round with no newer comment counts nothing
- **WHEN** a round stopped the comment on an item at the cap, a second round runs, a person then replies, and a third round runs
- **THEN** the second round writes nothing, and the third round counts and logs one more stopped comment and records the reply's time

### Requirement: A person refines an item at the cap
`devops roadmap refine --item` SHALL refine the item it names at the cap on refine's comments, since a person asked for it, and SHALL count no stopped comment.

#### Scenario: A person refines an item at the cap
- **WHEN** a person runs `devops roadmap refine --item <number> --confirm` on an item at the cap
- **THEN** refine refines the item and posts its comment, and counts no stopped comment

### Requirement: Each Firecrawl search counts by its result
`firecrawl_search` SHALL add 1 to `devops_cli_firecrawl_searches_total` for each search, with the `result` `ok`, the HTTP status of a search that Firecrawl refused, or `error` for a search that got no answer or a reply with no web results. A failed search SHALL log one warning that names the status or the error class, and SHALL NOT log the key or the query.

#### Scenario: Firecrawl has no credits
- **WHEN** Firecrawl answers a search with HTTP 402
- **THEN** the counter has one point with the result `402`, and one warning says `Firecrawl answered with HTTP 402` and holds neither the key nor the query

#### Scenario: No answer
- **WHEN** the search times out at the connect
- **THEN** the counter has one point with the result `error`, and the warning names `ConnectTimeout`
