# Design

## Decisions
- **Observer payload over ledger queries**: Forward `cache_read_tokens` and `cache_write_tokens` directly from `track_request_spend` into `_notify_call_observers` so `RunUsage` stays decoupled from SQLite (`SpendLedger`).
- **Keep full `input_tokens` plus separate cache totals**: Sum full `prompt_tokens` into `RunUsage.input_tokens` alongside `cache_read_tokens` and `cache_write_tokens`, matching `pricing.calculate_request_cost`'s contract (`cache_read_tokens` and `cache_write_tokens` are subsets of `prompt_tokens`).
- **Skip cached hits completely**: Preserve `if call.get("cached"): return` in `RunUsage.add` before reading any token counts so response-cache hits add zero tokens or cache counts.

## Rejected alternatives
- **Subtract cache tokens from `input_tokens`**: Double-discounts because `calculate_request_cost` already treats cache counts as parts of `prompt_tokens`.
- **Query SQLite from `RunUsage`**: Bypasses `observe_llm_calls` and couples eval reporting to ledger storage.
