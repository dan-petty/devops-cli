# Tasks

## 1. Behavior

- [x] 1.1 Write failing test for gateway endpoint classification
  - Verification: `$ uv run devops ci test tests/ai/spend/test_ai_spend_pricing.py`
- [x] 1.2 Implement `is_gateway_server` and update `is_local` in `pricing.py`
  - Verification: `$ uv run devops ci test tests/ai/spend/test_ai_spend_pricing.py`
- [x] 1.3 Update `factory.py` to handle gateway proxy endpoints
  - Verification: `$ uv run devops ci test tests/ai/client/test_agent_factory.py`

## 2. Documents

- [x] 2.1 Update docstrings and verify docs
  - Verification: `$ uv run devops ci docs`
