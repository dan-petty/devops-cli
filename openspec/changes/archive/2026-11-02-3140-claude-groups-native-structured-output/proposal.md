# Proposal

## Why

Issue #3140: the Claude gateway groups of #3117 cannot serve a call that asks for a structured reply, which is how the stage, refine and intake jobs call a model. LiteLLM turns `response_format` into a forced tool call unless its model map says that the model supports native structured output. The cost map of the pinned image lists no Claude 5.5 model, so LiteLLM takes the tool path, and the Anthropic API answers HTTP 400 for Sonnet 5.5: `tool_choice: type "tool" and "any" are not supported for this model`.

## Feasibility

- `devops roadmap eval stage --model claude-sonnet-5-5` ended 16 of 16 cases with `AIClientError` and that message, about 3 seconds per case.
- A local LiteLLM proxy of the pinned version (v1.103.0) with the config of the group reproduces the 400 for a `tool_choice` of `required` and for a `response_format`.
- With `supports_native_structured_output: true` and `supports_response_schema: true` in the `model_info` of the group, the debug log shows LiteLLM sending `output_format`, and both models answer a `response_format` request with valid JSON. Sonnet 5.5 staged 3 of 4 stage cases on that proxy (before: 0 of 16), Haiku 5.5 staged 1 of 4.
- `additional_drop_params: [tool_choice]` also removes the forced tool call, but the structured reply then rests on the model choosing the tool. The native format is the supported path, so the change uses it.

## Existing Tool Considered

LiteLLM already reads these two flags from the model map. No new tool.

## What Changes

- `k8s/llm/gateway/config.yaml`: the `model_info` of `claude-sonnet-5-5` and `claude-haiku-5-5` sets both flags.
- The hosted-group check in `tests/ai/benchmark/test_k8s_llm_gateway.py` fails when a Claude group lacks either flag, with one broken edit as proof.
- `k8s/README.md` names the flags.
- The change modifies one requirement of `ai-gateway-routing`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-gateway-routing`: the requirement `A Claude group sets its prices and drops refused parameters` also requires the two flags.

## Impact

- The gateway Deployment rolls when Argo CD syncs the ConfigMap. A structured call to a Claude group then works.
- No other group changes.
