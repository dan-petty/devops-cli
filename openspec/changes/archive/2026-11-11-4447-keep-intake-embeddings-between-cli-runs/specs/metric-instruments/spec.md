## MODIFIED Requirements

### Requirement: Embedding cache lookups count each text once
`devops_cli_embedding_cache_lookups_total` SHALL count each text that an embedding request looks up, one time, by `result`: `hit` or `miss`. A hit SHALL also carry `tier`: `memory` for the in-process cache, `valkey` for the Valkey cache, or `disk` for the disk cache. A request SHALL add a value only for a result that has texts. No other metric SHALL count embedding cache hits or misses.

#### Scenario: Three hits and two misses
- **WHEN** an embedding request gets five texts, three of which the in-process cache holds
- **THEN** `devops_cli_embedding_cache_lookups_total` gets the points `{result="hit", tier="memory"}` 3 and `{result="miss"}` 2, one time each

#### Scenario: A hit from Valkey
- **WHEN** an embedding request gets one text that only the Valkey cache holds
- **THEN** `devops_cli_embedding_cache_lookups_total` gets the one point `{result="hit", tier="valkey"}` 1

#### Scenario: A hit from the disk cache
- **WHEN** an embedding request gets two texts, one of which only the disk cache holds
- **THEN** `devops_cli_embedding_cache_lookups_total` gets the points `{result="hit", tier="disk"}` 1 and `{result="miss"}` 1, one time each
