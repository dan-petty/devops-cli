# Tasks

## 1. Count a hosted gateway group as hosted

Kind: behavior.

Reads: `src/devops_cli/ai/spend/pricing.py` (`is_local`, `calculate_request_cost`), `src/devops_cli/ai/spend/ledger.py` (`_QUERY_SERVED_USAGE`, `_tally_and_annotate_servers`), `src/devops_cli/lang/en/messages.py` (`hosted_model_unpriced`). Changes: the same files, `tests/ai/spend/test_ai_spend_pricing.py`, `tests/ai/spend/test_ai_spend_ledger.py` and `tests/ai/benchmark/test_k8s_llm_gateway.py`.

- [x] 1.1 Add the failing tests: `is_local` of a reply with a deployment model and no backend, the price of the Claude and Gemini groups behind a loopback gateway, the warning and the override of the DeepSeek group, the lifetime report, and the gateway config check that each local deployment sets `api_base`
- [x] 1.2 Make `is_local` read the deployment model, pass it from `calculate_request_cost` and the report, and name the command in the warning
  - Verification: `uv run devops ci test tests/ai/spend tests/ai/benchmark/test_k8s_llm_gateway.py`
- [x] 1.3 Regenerate the documentation with `uv run devops docs generate --sync-readme`. No generated document holds the message, so no file changes
  - Verification: `uv run devops ci docs`

## Workflow follow-up

- Pending a person: set the price of the group `deepseek-v4.1-flash-1017` with `devops ai cost set-price`.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
