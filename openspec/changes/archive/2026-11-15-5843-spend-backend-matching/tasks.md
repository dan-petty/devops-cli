# Tasks

## 1. Behavior

- [x] 1.1 Support `local/` prefix and provider prefixes in pricing and gateway models
  - Verification: `$ uv run devops ci test tests/ai/spend/test_ai_spend_pricing.py`
- [x] 1.2 Restrict local savings to `*.local`, loopback, and local transports
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_instruments.py`

## 2. Documents

- [x] 2.1 Update `ai-spend-pricing` spec requirements and scenarios
  - Verification: `$ uv run devops openspec check`
