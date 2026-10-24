# Tasks

## 1. Provider-Reported Stream Usage and Lifecycle Handling

- [ ] 1.1 Write failing tests for provider stream usage, multi-node Ollama leased server, and stream generator exit handling (`uv run devops ci test tests/test_ai_streaming.py`).
- [ ] 1.2 Implement stream options in OpenAI requests, stream usage extraction in stream readers, leased server tracking in Ollama, and `finally` spend recording in `unified.py` (`uv run devops ci test tests/test_ai_streaming.py`).
- [ ] 1.3 Update generated documentation (`uv run devops docs generate --sync-readme`).

## 2. Reasoning Tokens in LLMResponse, Ledger, and Telemetry

- [ ] 2.1 Write failing tests for reasoning tokens in `LLMResponse`, SQLite spend ledger schema evolution, and OpenTelemetry reasoning attributes (`uv run devops ci test tests/test_ai_spend_ledger.py tests/test_ai_client_telemetry.py`).
- [ ] 2.2 Implement `reasoning_tokens` on `LLMResponse`, parse reasoning in `openai.py`, add `reasoning_tokens` column to `ai_spend_records`, update `track_request_spend`, and emit telemetry (`uv run devops ci test tests/test_ai_spend_ledger.py tests/test_ai_client_telemetry.py`).
- [ ] 2.3 Update generated documentation (`uv run devops docs generate --sync-readme`).

## 3. Reasoning Share in Cost Reporting

- [ ] 3.1 Write failing tests for the reasoning-share column in `devops ai cost report` and `--by backend` (`uv run devops ci test tests/test_ai_spend_cli.py`).
- [ ] 3.2 Implement reasoning share reporting across backend tables and models in `ai_cost.py` and `src/devops_cli/ai/spend/models.py` (`uv run devops ci test tests/test_ai_spend_cli.py`).
- [ ] 3.3 Update generated documentation (`uv run devops docs generate --sync-readme`).

## Workflow follow-up

- Per-route token budgets and reasoning effort limits belong to follow-up issue #479.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
