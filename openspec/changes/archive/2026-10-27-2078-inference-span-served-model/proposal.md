# Proposal

## Why

Issue #2078: for a gateway call, the `ai.llm.dispatch` inference span sets `gen_ai.response.model` to the route name that the reply body names, such as `devops-chat`. The OpenTelemetry GenAI conventions define `gen_ai.response.model` as the name of the model that generated the response. Since #2031, devops-cli reads the deployment model that served a gateway call from the `x-litellm-model-name` reply header into `LLMResponse.served_model` for pricing, but the span does not use it, so the span names the route, not the model.

## What Changes

- `_set_response_span_attributes` in `src/devops_cli/ai/client/unified.py` sets `gen_ai.response.model` to the deployment model `LLMResponse.served_model` when the gateway reply names one, and to the reply-body model `LLMResponse.model` when it names none. The single writer of the response model key stays the only writer, so the request's tokens are still counted once.
- `gen_ai.request.model` keeps the model the client asked for, the route name for a gateway call. It is set from `self._config.model` and changes no value.
- `ai.llm.stream` changes no value. It carries no `gen_ai.response.model`, as before.
- The value of the `gen_ai.response.model` attribute of the inference span changes for a gateway call, so the change has a spec delta. It adds a requirement to `llm-telemetry-content`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `llm-telemetry-content`: adds the requirement that the `ai.llm.dispatch` inference span names the deployment model that served a gateway call as `gen_ai.response.model`, and keeps the reply-body model when the gateway names none.

## Impact

- Code: `src/devops_cli/ai/client/unified.py`, `_set_response_span_attributes`.
- Tests: `tests/test_ai_client_telemetry.py`.
- No dependency, command, option, metric or message changes.

## Feasibility

- LiteLLM 1.103.0 source, confirmed in #2031: `ProxyBaseLLMRequestProcessing.get_custom_headers` sets `x-litellm-model-name` to the deployment's `litellm_params.model`, while the router writes the model-group alias that the client asked for, the route name, in the reply `model` field. Thus `LLMResponse.served_model` and `LLMResponse.model` differ for a hosted gateway call, and they match when no gateway names a deployment model.
- OpenTelemetry GenAI conventions, pinned in `src/devops_cli/telemetry/semconv_genai.json`: `gen_ai.response.model` is the name of the model that generated the response. `tests/test_telemetry_semconv.py` accepts both `gen_ai.request.model` and `gen_ai.response.model`, so no snapshot change.
- `LLMResponse.served_model` already carries the header value (#2031): `extract_served_model` reads `CONST_AI_GATEWAY_SERVED_MODEL_HEADER` (`x-litellm-model-name`), and the spend path in `unified.py` already prefers `served_model` over `model`.
- On the base commit, the new test fails: `gen_ai.response.model` holds the route name, not the deployment model that the reply header names.

## Existing Tool Considered

- The GenAI span attributes are devops-cli's own telemetry, written to the OpenTelemetry conventions the project already pins. This change aligns the value of one existing attribute with its convention; it names no replacement tool and adds no code to build in its place.
- The change deletes no code. It changes the value written for `gen_ai.response.model` in `_set_response_span_attributes`.
