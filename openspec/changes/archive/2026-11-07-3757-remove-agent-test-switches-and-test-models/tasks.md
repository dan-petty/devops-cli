# Tasks

## 1. The floor proves the model edge (test)

- [x] 1.1 Add the test in `tests/invariants/test_hermetic_floor.py`: an inner test with no `model_fake` errors at teardown and names the unfaked edge, and an inner test with `model_fake` passes with one recorded call
  - Verification: `uv run pytest tests/invariants/test_hermetic_floor.py -k model_call`

## 2. The test model leaves src (refactor)

- [x] 2.1 Delete the `"test"` branch of `resolve_pydantic_ai_model`, drop the `"test"` string case of `test_resolve_pydantic_ai_model`, and pass `TestModel()` in `test_dual_compatibility_with_devops_cli_pydantic_agent`
  - Verification: `uv run pytest tests/ai/agents/test_pydantic_agent.py tests/ai/agents/test_pydantic_ai_native_capabilities.py`
- [x] 2.2 Take the registry of the embedding cost test from `get_pricing_registry(data_dir=tmp_path)` with no patch and no spy, and add the provider and request time test of `PricingRegistry.calculate_request_cost`
  - Verification: `uv run pytest tests/ai/agents/test_ai_agent_capabilities.py tests/ai/spend/test_ai_spend_pricing.py`

## 3. Check and archive

- [x] 3.1 Check that the change folder is valid
  - Verification: `uv run devops openspec check`
