# Proposal: #5578

## Why
`track_request_spend` records `cache_read_tokens` and `cache_write_tokens` in SQLite, but `_notify_call_observers` omits both fields and `RunUsage` does not accumulate or pass them to `calculate_request_cost`. Live `devops roadmap eval stage` runs therefore price every prompt token at full input rate instead of cached rates.

## What Changes
- Include `cache_read_tokens` and `cache_write_tokens` in the call dictionary sent to `_notify_call_observers` in `src/devops_cli/ai/spend/ledger.py`.
- Add `cache_read_tokens: int = 0` and `cache_write_tokens: int = 0` fields to `RunUsage` in `src/devops_cli/roadmap/stage/stage_eval_usage.py`, sum them in `RunUsage.add` for non-cached calls, and forward them to `calculate_request_cost` in `RunUsage.spend_usd`.

## Capabilities
- `ai-spend-pricing`: Expose cache read and cache write token counts to `observe_llm_calls` observers.
- `roadmap-stage-eval`: Sum cache token counts across non-cached calls in `RunUsage` and price eval runs with cache rates.

## Impact
- `src/devops_cli/ai/spend/ledger.py`
- `src/devops_cli/roadmap/stage/stage_eval_usage.py`
- `tests/ai/spend/test_ai_spend_ledger.py`
- `tests/roadmap/stage/test_roadmap_stage_eval_usage.py`

## Feasibility
Confirmed against `origin/main`: `ledger.py:1053` omits `cache_read_tokens` and `cache_write_tokens`, `stage_eval_usage.py:21-38` lacks both fields and calls `calculate_request_cost(model, self.input_tokens, self.output_tokens)` without cache kwargs, while `pricing.py:827` already supports both kwargs and `claude-sonnet-5-5` returns a lower cost when cache tokens are passed.

## Existing Tool Considered
`pydantic/genai-prices` is already in use via `calculate_request_cost` (`src/devops_cli/ai/spend/pricing.py:827`) and already prices cache read and cache write tokens; only wiring the counts through `_notify_call_observers` and `RunUsage` is missing.
