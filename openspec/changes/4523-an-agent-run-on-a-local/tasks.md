# Tasks

## 1. The group that answered decides the locality of a gateway call (behavior)

- [x] 1.1 Write failing tests: `is_local` for a reply that names a local group, an `ollama:` model, a hosted group and another deployment model, and for an asked local group whose reply names no model
  - Verification: `$ uv run devops ci test tests/ai/spend/test_ai_spend_pricing.py`
- [x] 1.2 Write failing tests: `record_run_spend` on `devops-coder` whose reply names `devops-coder` records `local`, 0 USD, the token label `local` `true` and no warning; a fallback is priced at the group that answered
  - Verification: `$ uv run devops ci test tests/ai/client/test_roadmap_agent_run.py`
- [x] 1.3 Give `is_local` the asked model, and let a local group or an `ollama:` model that the reply or the asked model names make a gateway call local; `calculate_request_cost` passes the asked model
  - Verification: `$ uv run devops ci test tests/ai/spend/test_ai_spend_pricing.py tests/ai/client/test_roadmap_agent_run.py tests/ai/spend/test_ai_spend_ledger.py`

## Workflow follow-up

- A gateway reply that names a local group outside `CONST_AI_GATEWAY_VIRTUAL_MODELS`, such as `qwen3.8:27b`, or the Ollama model of a local fallback, such as `ollama_chat/qwen3.8:27b`, still counts as hosted: #4886.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
