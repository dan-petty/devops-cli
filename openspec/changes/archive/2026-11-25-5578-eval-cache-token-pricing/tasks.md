# Tasks

## 1. Behavior

- [x] 1.1 Add failing tests for cache token observer fields and `RunUsage` cache pricing in `tests/ai/spend/test_ai_spend_ledger.py` and `tests/roadmap/stage/test_roadmap_stage_eval_usage.py`
  - Verification: `$ uv run devops ci test tests/ai/spend/test_ai_spend_ledger.py tests/roadmap/stage/test_roadmap_stage_eval_usage.py`
- [x] 1.2 Forward `cache_read_tokens` and `cache_write_tokens` in `_notify_call_observers` (`ledger.py`) and accumulate/price them in `RunUsage` (`stage_eval_usage.py`)
  - Verification: `$ uv run devops ci test tests/ai/spend/ tests/roadmap/stage/`

## 2. Documents

- [x] 2.1 Verify OpenSpec and docs checks pass
  - Verification: `$ uv run devops openspec check && uv run devops ci docs`
