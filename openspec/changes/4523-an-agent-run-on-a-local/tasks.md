# Tasks

## 1. The group that answered decides the locality of a gateway call (behavior)

- [ ] 1.1 Write failing tests: `is_local` for a reply that names a local group, an `ollama:` model, a hosted group and another deployment model, and for an asked local group whose reply names no model
  - Verification: `$ uv run devops ci test tests/ai/spend/test_ai_spend_pricing.py`
- [ ] 1.2 Write failing tests: `record_run_spend` on `devops-coder` whose reply names `devops-coder` records `local`, 0 USD, the token label `local` `true` and no warning; a fallback is priced at the group that answered
  - Verification: `$ uv run devops ci test tests/ai/client/test_roadmap_agent_run.py`
- [ ] 1.3 Give `is_local` the asked model, and let a local group or an `ollama:` model that the reply or the asked model names make a gateway call local; `calculate_request_cost` passes the asked model
  - Verification: `$ uv run devops ci test tests/ai/spend/test_ai_spend_pricing.py tests/ai/client/test_roadmap_agent_run.py tests/ai/spend/test_ai_spend_ledger.py`

## Workflow follow-up

- A local fallback whose reply names a LiteLLM Ollama reference (`ollama_chat/<model>`) or the bare Ollama model, and no gateway group, still counts as hosted. Follow-up issue: see the pull request comment.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
