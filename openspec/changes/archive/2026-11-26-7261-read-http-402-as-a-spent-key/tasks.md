# Tasks

## 1. Behavior: an HTTP 402 is a spent provider key

- [x] 1.1 Write failing tests: `spend_limit_error` gives `AIKeySpendLimitError` for a 402 with each body; `model_call_error` gives it for `ModelHTTPError` 402 and for `ModelQuotaExceededError` with and with no HTTP status; the failure class of the error is `spend_limit`; a 429 of the gateway cooldown keeps `AIClientError` and the class `provider`; a gateway chat and stream of `LLMClient` and a Claude status error with 402 raise the error; the stage agent ends in `spend_limit` for a 402; an implement step raises the error for a 402 quota error and resets the checkout
  - Verification: `$ uv run devops ci test tests/ai/client/test_ai_client_spent_credits.py tests/roadmap/stage/test_roadmap_stage_agent_phase.py tests/roadmap/implement/test_roadmap_implement_step.py`
- [x] 1.2 Add `PAYMENT_REQUIRED`, `KEY_STOP_STATUSES` and `spent_key_error` to `ai/client/models.py`, give a 402 the spend-limit error in `spend_limit_error`, read the set at the status branches of `LLMClient`, and map the status and `ModelQuotaExceededError` in `model_call_error`
  - Verification: `$ uv run devops ci test tests/ai/client/test_ai_client_spent_credits.py tests/ai/client/test_ai_client_spend_limit.py tests/roadmap/stage/test_roadmap_stage_agent_phase.py tests/roadmap/implement/test_roadmap_implement_step.py tests/roadmap/test_roadmap_failure.py`

## 2. Documents

- [x] 2.1 Name HTTP 402 in the row `spend_limit` of docs/ROADMAP_WORKFLOW.md and in the row `RoadmapProviderKeySpendLimit` of docs/CLUSTER.md
  - Verification: `$ uv run devops ci docs`
