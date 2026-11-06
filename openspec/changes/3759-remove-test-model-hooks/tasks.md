# Tasks

## 1. The tests run on the model fake (other)

- [x] 1.1 In `tests/ai/agents/test_ai_agent_capabilities.py`, `tests/ai/mcp/test_pydantic_ai_mcp.py` and `tests/ai/models/test_pydantic_ai_ollama.py`, answer from the `model_fake` fixture and not from the home-made `TestModel`. Drop the tests of the removed utilities and of the flag.
  - Verification: `uv run pytest tests/ai/agents/test_ai_agent_capabilities.py tests/ai/mcp/test_pydantic_ai_mcp.py tests/ai/models/test_pydantic_ai_ollama.py`
- [x] 1.2 Remove the patch of `_is_testing_mode_active` from the three gateway tests, and the test of `TestModel.__test__` from the invariants.
  - Verification: `uv run pytest tests/ai/client/test_gateway_caller_headers.py tests/ai/test_pydantic_ai_profiles_and_providers.py tests/roadmap/test_roadmap_implement_step_output_cap.py tests/invariants`

## 2. The hooks leave src (other)

- [x] 2.1 Delete `ai/agents/testing.py`, `ALLOW_MODEL_REQUESTS` and its check in `ai/agents/agent.py`, the two capture blocks in `PydanticAgent`, and `_is_testing_mode_active` in `ai/pydantic_ai_bridge.py`. Remove the module from `CONST_DOMAIN_EXCEPTION_MODULES`.
  - Verification: `! git grep -nE 'ALLOW_MODEL_REQUESTS|ModelNotAllowedError|MODEL_REQUESTS_DISABLED|_RUN_MESSAGES_CAPTURE|_is_testing_mode_active|agents\.testing' -- src tests docs ':!docs/agent/archive'`
- [x] 2.2 Remove the `ModelNotAllowedError` row from `docs/ERRORS.md`.
  - Verification: `uv run devops docs generate --check`

## 3. Check the change

- [x] 3.1 Check that the change folder is valid
  - Verification: `uv run devops openspec check`

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
