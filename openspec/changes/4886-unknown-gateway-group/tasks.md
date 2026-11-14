# Tasks

## 1. Name the local gateway groups

Reads: `src/devops_cli/ai/spend/pricing.py`. Changes: the same file, the constants, and `tests/ai/spend/test_hosted_group_prices.py`.

- [ ] 1.1 Add `CONST_AI_GATEWAY_LOCAL_GROUPS`.
- [ ] 1.2 Accept the local groups and the Ollama prefixes.
- [ ] 1.3 Add the test that compares the constant with the gateway config.
  - Verification: `$ uv run devops ci test tests/ai/spend/test_hosted_group_prices.py` passes
