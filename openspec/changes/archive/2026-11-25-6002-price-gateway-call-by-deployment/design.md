# Design

## Decisions
1. **Capture `x-litellm-model-name` via an `httpx2` response event hook + `ContextVar`:**
   `create_pydantic_ai_provider(..., gateway_caller=True)` (`src/devops_cli/ai/providers/__init__.py:177-179`) already installs `event_hooks={"request": [name_gateway_caller]}` on the gateway `AsyncClient`. Adding `"response": [capture_gateway_served_model]` writes `extract_served_model(response.headers)` into `gateway_served_model` (`ContextVar[str | None]`, `src/devops_cli/ai/client/network.py`). Each response overwrites the context variable (writing `None` when the header is absent), so retries do not carry stale headers from an earlier attempt.
2. **Store the captured header per call on `GatewayCallModel.served_model`:**
   `GatewayCallModel` (`src/devops_cli/ai/models/gateway.py:79-119`) sets `self.served_model: str | None = None`, resets both `self.served_model` and `gateway_served_model` before `request` and `request_stream`, captures `gateway_served_model.get()` into `self.served_model` once the call/stream opens, and resets `gateway_served_model` in `finally`. `WrapperModel.__getattr__` automatically exposes `.served_model` when `ConcurrencyLimitedModel` wraps `GatewayCallModel`.
3. **Prefer `served_model` on the model object in both agent spend paths without altering answer counters:**
   `_spend_capability` (`src/devops_cli/ai/client/factory.py:213-227`) and `record_run_spend` (`src/devops_cli/roadmap/agent_run.py:599-619`) read `getattr(model, "served_model", None)` for `served_model`, falling back to the reply body `model_name` when `None`. `AI_MODEL_ANSWERS_TOTAL` keeps `response.model_name`, so gateway group fallbacks keep reporting `fallback="false"` for same-group routing.

## Rejected alternatives
- **Read `response.model_name` from the JSON reply body:** Rejected because LiteLLM sets the body's `model` field to the requested group alias (`src/devops_cli/ai/client/network.py:173-174`), causing order-2 calls to be billed at order-1 rates.
- **Pass an unverified LiteLLM 1.103.11 request flag:** Rejected because no codebase evidence or tested configuration verifies a flag that rewrites body `model` across streaming and non-streaming calls, whereas `x-litellm-model-name` is already active and used by `extract_served_model` (`k8s/README.md:115`, `network.py:169`).
- **Add a multiplier or second price row in `pricing.py`:** Rejected because `src/devops_cli/ai/spend/pricing.py:71-94` already contains `_DEEPSEEK_V4_1_FLASH_PRICE` keyed by `openrouter/deepseek/deepseek-v4.1-flash`, guarded by `tests/ai/spend/test_hosted_group_prices.py`.
- **Fail or omit spend rows when `x-litellm-model-name` is absent:** Rejected because streamed gateway responses past an SSE keepalive ping intentionally omit `x-litellm-*` headers (`k8s/README.md:115`); falling back to the body group preserves billing coverage.
