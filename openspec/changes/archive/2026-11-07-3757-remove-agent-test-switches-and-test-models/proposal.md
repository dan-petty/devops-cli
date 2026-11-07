# Proposal

## Why

Product code in `src` must hold no test switch and no test model (#3757, child of #1330, ADR 0007). Change #3759 removed most of the agent switches. Two parts stay:

- `resolve_pydantic_ai_model` in `ai/pydantic_ai_bridge.py` builds a pydantic-ai `TestModel` when the model name is the string `"test"`. Only two tests pass that name. The branch is a test model in `src`.
- Three tests of the work list of #3757 still hold a patch or a gap:
  - `test_embedding_cost_of_a_local_model_is_zero_whatever_its_custom_price` patches `devops_cli.ai.spend.get_pricing_registry` and spies on `calculate_request_cost`.
  - `test_resolve_pydantic_ai_model` and `test_dual_compatibility_with_devops_cli_pydantic_agent` pass the string `"test"`.
  - No test proves that the hermetic floor fails a model call that has no `model_fake`.

## What Changes

- Delete the `model == "test"` branch of `resolve_pydantic_ai_model`, and its mention in the docstring.
- `test_resolve_pydantic_ai_model` loses its `"test"` string case. `test_dual_compatibility_with_devops_cli_pydantic_agent` passes a `TestModel()` instance.
- The embedding cost test takes its registry from `get_pricing_registry(data_dir=tmp_path)`, patches no name and spies on no method. A new test of `PricingRegistry.calculate_request_cost` holds the check that the provider and the request time reach the cost.
- A new test in `tests/invariants/test_hermetic_floor.py` runs two inner tests through the floor. The one with no `model_fake` errors at teardown and names the unfaked edge. The one with `model_fake` passes and records one call.
- The change alters no behavior that a consumer observes. No command passes the model name `"test"`. So it has no spec delta and sets `skip_specs: true`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Source: `ai/pydantic_ai_bridge.py`.
- Tests: `tests/ai/agents/test_pydantic_agent.py`, `tests/ai/agents/test_pydantic_ai_native_capabilities.py`, `tests/ai/agents/test_ai_agent_capabilities.py`, `tests/ai/spend/test_ai_spend_pricing.py`, `tests/invariants/test_hermetic_floor.py`.
- The change fits one pull request.

## Feasibility

Checked at origin/main 734e060b with `git grep` and with a run of the floor through `pytester`:

- Change #3759 (commit 9b018214) already did most of #3757. `ai/agents/testing.py` does not exist. A `git grep` for `ALLOW_MODEL_REQUESTS`, `ModelNotAllowedError`, `MODEL_REQUESTS_DISABLED`, `_RUN_MESSAGES_CAPTURE`, `_is_testing_mode_active` and `agents.testing` over `src`, `tests` and `docs` (not `docs/agent/archive`) returns no line. `docs/ERRORS.md` and `CONST_DOMAIN_EXCEPTION_MODULES` name nothing deleted. The patches of `_is_testing_mode_active`, the "Offline test mode bypass" block and `test_test_model_pytest_collection_disabled` are gone. So this change does not repeat that work.
- The `"test"` branch of `resolve_pydantic_ai_model` stays after #3759 and is the first part of this change. Only `tests/ai/agents/test_pydantic_agent.py` and `tests/ai/agents/test_pydantic_ai_native_capabilities.py` use it.
- Premise check of the model-fake edge error. An inner test that calls `get_llm_client().chat(...)` with no `model_fake` reaches the keyring edge `devops-cli/ai_api_key` and then the Ollama port. The floor fails that test at teardown with "network edge reached without a fake". The call itself raises `AIClientError` in the inner test, so the inner test catches the error, as the other floor tests do. The call takes `chat(system, user)`, not `chat("x")` as the issue text writes it. The inner test also takes the `clock` fixture, or the client retry waits 15 s in real time. A second inner test with `model_fake` passes and records one call.
- `PricingRegistry.calculate_request_cost` decides locality from the provider and the rate from the request time. A DeepSeek model costs 0.27 USD for 1 000 000 tokens at 12:00 UTC and 0.135 USD at 20:00 UTC. A custom price of `local-embed` costs 0 USD for provider `ollama` and 0.15 USD for provider `openai` at 100 000 tokens. These values come from a run of the registry.

## Existing Tool Considered

pydantic-ai `TestModel` (https://pydantic.dev/docs/ai/guides/testing/), the project fake `model_fake`, the `pytester` pattern of `tests/invariants/test_hermetic_floor.py` and the `clock` fixture cover every use. No new code is built, and the change deletes code. Cost: about 80 000 tokens to change and check, about 0 tokens to keep, and about 1 hour elapsed.
