# Tasks

## 1. Gateway agent deployment-model spend capture (behavior)

- [x] 1.1 Write failing tests in `tests/ai/client/test_agent_factory.py` and `tests/ai/client/test_roadmap_agent_run.py` for order-2 `x-litellm-model-name` deployment pricing, missing-header fallback, `AI_MODEL_ANSWERS_TOTAL` group labels, and chat deployment pricing.
  - Verification: `$ uv run pytest -n 0 tests/ai/client/test_agent_factory.py tests/ai/client/test_roadmap_agent_run.py -k "deployment_header or order_2 or missing_header"`
- [x] 1.2 Add `gateway_served_model` + `capture_gateway_served_model` in `src/devops_cli/ai/client/network.py`, install the response hook in `src/devops_cli/ai/providers/__init__.py`, store `served_model` per call on `GatewayCallModel` in `src/devops_cli/ai/models/gateway.py`, read it in `src/devops_cli/ai/client/factory.py` and `src/devops_cli/roadmap/agent_run.py`, and update the `_HOSTED_GROUP_PRICES` comment in `src/devops_cli/ai/spend/pricing.py`.
  - Verification: `$ uv run pytest -n 0 tests/ai/client/test_agent_factory.py tests/ai/client/test_roadmap_agent_run.py tests/ai/models/test_gateway_call.py tests/ai/retries/test_pydantic_ai_retries.py tests/ai/spend/`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
