## ADDED Requirements

### Requirement: RunUsage prices cache read and cache write tokens
`RunUsage.add` SHALL add `cache_read_tokens` and `cache_write_tokens` on non-cached calls and ignore all counts on cached calls; `RunUsage.spend_usd` SHALL pass both cache totals to `calculate_request_cost`.

#### Scenario: Cache counts sum across non-cached calls and skip cached calls
- **WHEN** `RunUsage.add` processes two non-cached calls with cache read/write counts `(100, 10)` and `(200, 20)` plus a cached call with non-zero counts
- **THEN** `RunUsage` holds `cache_read_tokens == 300` and `cache_write_tokens == 30` and ignores the cached call

#### Scenario: Eval run spend uses cache rates
- **WHEN** `RunUsage` holds 10,000 input tokens, 1,000 output tokens, 8,000 cache read tokens, and 1,000 cache write tokens for `claude-sonnet-5-5`
- **THEN** `spend_usd` equals `calculate_request_cost` for all four counts and is strictly less than with zero cache counts
