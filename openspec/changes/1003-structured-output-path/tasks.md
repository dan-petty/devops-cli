# Tasks

## 1. One structured-output path

- [x] Add a failing invariant test: no module other than `ai/client/structured.py` and `ai/schema_reflection.py` builds a schema reflection
  - Verification: `uv run devops ci test tests/invariants/test_source_tree.py`
- [x] `chat_structured` uses `build_schema_reflection_message`, and its own copy is deleted
  - Verification: `uv run devops ci test tests/test_ai_client_structured.py tests/test_schema_reflection.py`
- [x] Delete the agent loop's schema arm (`output_type`, `output_schema`, `output_json_schema`, `output_validator`, the runner helpers, `AgentRetries.output`, `AgentSpec.output_schema`, `AgentInfo.output_schema`) and its tests
  - Verification: `uv run devops ci test tests/test_pydantic_agent.py tests/test_pydantic_ai_concurrency.py tests/test_batch_2_review_defects.py`
- [x] Delete the schema arm of `fix_llm_response` and `ai/output/`, and their tests
  - Verification: `uv run devops ci test tests/test_ai_fixer.py tests/test_schema_reflection.py`
- [x] Delete `MultiAgentPipeline.output_schema`, `_parse_pipeline_output`, `final_data`, `parsed_data` and the type parameter
  - Verification: `uv run devops ci test tests/test_agent.py tests/test_pipeline_context_budget.py tests/test_pydantic_ai_concurrency.py`
- [x] Cover the changed lines through the public interface: an integer `retries` sets the tool retry budget, and a pipeline with no agents returns an empty result
  - Verification: `uv run devops ci test tests/test_pydantic_agent.py tests/test_pydantic_ai_concurrency.py`
- [x] Lower the swallowed-failure ceilings to the new counts
  - Verification: `uv run devops ci test tests/test_swallowed_failures_ratchet.py`
- [x] Correct the knowledge-base page on `PydanticAgent`, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 1003-structured-output-path`

## Workflow follow-up

- #1419 adds the wire constraint of the claude, openai and copilot providers to `chat_structured`'s request.
- #1005 decides whether to adopt the native `pydantic_ai.Agent`, whose `output_type` would bring structured agent replies back through pydantic-ai.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
