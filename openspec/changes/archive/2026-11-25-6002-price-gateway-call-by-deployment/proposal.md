# Proposal: #6002

## Why
After `#5995`, the `deepseek-v4.1-flash-1017` gateway group routes between order 1 (`openrouter/deepseek/deepseek-v4.1-flash-1017`, `0.0784` USD input per million) and order 2 (`openrouter/deepseek/deepseek-v4.1-flash`, `0.3` USD input per million). LiteLLM returns the requested group alias in the reply body's `model` field and puts the deployment that actually answered in the `x-litellm-model-name` response header. Blocking and streamed `LLMClient` calls already read `x-litellm-model-name`, but agent runs (`_spend_capability` in `factory.py` and `record_run_spend` in `agent_run.py`) only read `response.model_name`, underpricing order-2 agent calls by ~4x (#6002).

## What Changes
- **Response Header Hook**: `src/devops_cli/ai/client/network.py` adds a `gateway_served_model` `ContextVar` and async `capture_gateway_served_model` response event hook calling `extract_served_model(response.headers)`. `src/devops_cli/ai/providers/__init__.py` installs it in `event_hooks["response"]` when `gateway_caller=True`.
- **GatewayCallModel**: `src/devops_cli/ai/models/gateway.py` resets `gateway_served_model` before each `request` and `request_stream`, captures `gateway_served_model.get()` onto `self.served_model`, and resets the context variable in `finally`.
- **Agent Spend Paths**: `src/devops_cli/ai/client/factory.py` (`_spend_capability`) and `src/devops_cli/roadmap/agent_run.py` (`record_run_spend`) pass `getattr(model, "served_model", None) or answered` to `track_request_spend` as `served_model`, while keeping `response.model_name` for `devops_cli_ai_model_answers_total`.
- **Documentation & Tests**: `src/devops_cli/ai/spend/pricing.py` updates the `_HOSTED_GROUP_PRICES` comment; `tests/ai/client/test_agent_factory.py` and `tests/ai/client/test_roadmap_agent_run.py` verify order-2 deployment pricing, missing-header fallback, `AI_MODEL_ANSWERS_TOTAL` group labels, and chat calls keeping deployment pricing.

This bug fix fits in one pull request and requires an OpenSpec delta because it changes observable client ledger pricing and spend telemetry for gateway agent runs.

## Capabilities
- Modified: `ai-spend-pricing`

## Impact
- Gateway agent runs answered by order-2 fallback deployments record the deployment model in `served_model` and accurate spend in `ai_spend_records` and `devops_cli_ai_spend_usd_total`.
- Replies without `x-litellm-model-name` (such as streams delayed past SSE keepalive pings) fall back cleanly to the reply body's model group.

## Feasibility
Confirmed against source on `origin/main`:
- `src/devops_cli/ai/client/network.py:169-178` already extracts `CONST_AI_GATEWAY_SERVED_MODEL_HEADER` (`x-litellm-model-name`).
- `src/devops_cli/ai/providers/__init__.py:168-181` already constructs the gateway `httpx2.AsyncClient` with `event_hooks={"request": [name_gateway_caller]}`.
- `src/devops_cli/ai/models/gateway.py:79-119` (`GatewayCallModel`) wraps gateway chat models in `pydantic_ai_bridge.py:181,222`, and `WrapperModel.__getattr__` forwards attribute lookups through `ConcurrencyLimitedModel`.
- `src/devops_cli/ai/client/factory.py:211-235` and `src/devops_cli/roadmap/agent_run.py:598-619` pass `response.model_name` directly as `served_model`.
- `src/devops_cli/ai/spend/pricing.py:71-95` already holds `"openrouter/deepseek/deepseek-v4.1-flash": _DEEPSEEK_V4_1_FLASH_PRICE` (`0.3` / `1.2` USD per million).

## Existing Tool Considered
BerriAI/litellm (in-use, `https://github.com/BerriAI/litellm`) already sets `x-litellm-model-name` on gateway HTTP responses and prices gateway-side spend per deployment, but provides neither `devops-cli`'s pydantic-ai response-header capture nor client spend ledger hooks. Building this client capture costs ~25,000 tokens (~3 hours elapsed), ~2,000 tokens/year to keep, and ~3,000 tokens to fix; it removes the client ledger's hardcoded reliance on reply-body `model_name` for `served_model` in agent runs.
