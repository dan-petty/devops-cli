# Proposal

## Why

Product code in `src` holds switches that only tests use (#3759, child A of #1330). Tests double only edges, and `src` must hold no test switch (ADR 0007).

- `ALLOW_MODEL_REQUESTS` is a flag in `ai/agents/agent.py` and in `ai/agents/testing.py`. `PydanticAgent.run` reads both and raises `ModelNotAllowedError` for a client that is not a home-made `TestModel` or `FunctionModel`.
- `_is_testing_mode_active` in `ai/pydantic_ai_bridge.py` reads the same flags, and `resolve_pydantic_ai_model` returns a pydantic-ai `TestModel` when it is true.
- `_RUN_MESSAGES_CAPTURE` is a `ContextVar` that `PydanticAgent` fills at the end of a run, for the home-made `capture_run_messages`.
- Nothing outside tests sets a flag or reads a capture. Both flags default to `True`, so the check never fires in the product.

## What Changes

- Delete `src/devops_cli/ai/agents/testing.py` (`ALLOW_MODEL_REQUESTS`, `ModelNotAllowedError`, `_RUN_MESSAGES_CAPTURE`, `capture_run_messages`, `AgentInfo`, `TestModel`, `FunctionModel`).
- Delete `ALLOW_MODEL_REQUESTS` and the check in `ai/agents/agent.py`, the two capture blocks in `PydanticAgent`, and `_is_testing_mode_active` in `ai/pydantic_ai_bridge.py`.
- Remove `devops_cli.ai.agents.testing` from `CONST_DOMAIN_EXCEPTION_MODULES`, and the `ModelNotAllowedError` row from `docs/ERRORS.md`.
- Move seven test files to the model seam that exists: the `model_fake` fixture (`tests/support/fakes/model.py`) replaces the home-made `TestModel`, and the lines that patched `_is_testing_mode_active` to false go (it was already false). The tests of the removed utilities and of the flag go with them.
- The change alters no behavior that a consumer observes: a flag that was always true and a module that only tests imported leave. So it has no spec delta and sets `skip_specs: true`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Source: `ai/agents/agent.py`, `ai/agents/testing.py` (deleted), `ai/pydantic_ai_bridge.py`, `config/constants.py`.
- Document: `docs/ERRORS.md`.
- Tests: `tests/ai/agents/test_ai_agent_capabilities.py`, `tests/ai/mcp/test_pydantic_ai_mcp.py`, `tests/ai/models/test_pydantic_ai_ollama.py`, `tests/ai/client/test_gateway_caller_headers.py`, `tests/ai/test_pydantic_ai_profiles_and_providers.py`, `tests/roadmap/test_roadmap_implement_step_output_cap.py`, `tests/invariants/test_architectural_invariants.py`.
- The change fits one pull request. It leaves children B to F of #1330 and the loop that #2489 deletes.

## Feasibility

Checked at origin/main 44d9196d with `git grep`:

- `git grep -nE 'ALLOW_MODEL_REQUESTS|ModelNotAllowedError|MODEL_REQUESTS_DISABLED|_RUN_MESSAGES_CAPTURE|_is_testing_mode_active|agents\.testing' -- src tests docs ':!docs/agent/archive'` lists the sites of this change and no other. Under `src` they are `agent.py`, `testing.py`, `pydantic_ai_bridge.py` and `constants.py`. Under `docs` the only site is `ERRORS.md`.
- The text of #1330 says 11 test files. The tree holds seven that name a hook. The count of #1330 is older than the tree. The seven files are the full list that the grep above finds.
- No test sets `ALLOW_MODEL_REQUESTS` to false outside the two tests that test the flag itself. The three tests that patch `_is_testing_mode_active` set it to false, which is its value already. So removing the patch changes nothing.
- `ModelFake` (the `model_fake` fixture) is the `LLMClient` stand-in that the factory seam installs, with `chat_messages`, queued answers and a record of each call. It covers every use of the home-made `TestModel`.
- The hermetic floor (`tests/conftest.py`, #1310) already fails a test that reaches a model or any network edge without a fake. So the refusal that `ModelNotAllowedError` gave in tests is held by the floor.
- `resolve_pydantic_ai_model("test")` stays. `test` is the name pydantic-ai gives to its own `TestModel`, and it is no test detection.

## Existing Tool Considered

pydantic-ai `TestModel` and `FunctionModel`, and the project fake `ModelFake`, cover every use. No new code is built, and the change deletes about 120 lines of own code. Cost: about 60,000 tokens to change and check, about 0 tokens to keep, and about 1 hour elapsed.
