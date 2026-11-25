## ADDED Requirements

### Requirement: Observer call record holds cache token counts
The call record passed to `observe_llm_calls` callbacks via `_notify_call_observers` SHALL include `cache_read_tokens` and `cache_write_tokens` from the tracked spend call.

#### Scenario: Observer sees cache counts
- **WHEN** `track_request_spend` records 1,200 `cache_read_tokens` and 300 `cache_write_tokens` while `observe_llm_calls` is active
- **THEN** the observer receives a dictionary with `cache_read_tokens == 1200` and `cache_write_tokens == 300`
