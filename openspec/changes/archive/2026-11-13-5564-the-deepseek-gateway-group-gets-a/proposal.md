# Proposal: #5564

## Why
The gateway group `deepseek-v4.1-flash-1017` has no fallback, so a failed route ends the call. On 2026-11-13 from about 22:10Z, its OpenRouter `floor` route timed out about 35 times in 30 minutes, and three stage Jobs failed with HTTP 504. The cheapest fp8 endpoint of the dated model, which `floor` picks, had an uptime of 33% in the last 30 minutes. Closes #5564.

## What Changes
- Add the hosted group `deepseek-v4.1-flash` (`openrouter/deepseek/deepseek-v4.1-flash`, no `floor` route, fp8, `data_collection: deny`, window 1,048,576) with the list prices of the model.
- Add the fallback `deepseek-v4.1-flash-1017` to `deepseek-v4.1-flash`.
- Price the new group in `_HOSTED_GROUP_PRICES` and name it in `CONST_AI_GATEWAY_HOSTED_MODELS`.
- Name the new group and the second fallback in SECURITY.md item 13 and in `k8s/README.md`.

## Capabilities
- `ai-gateway-routing`: a hosted DeepSeek group falls back to the undated model with the same provider filter.

## Impact
- The gateway rolls when Argo CD syncs the new `config.yaml`: the generated ConfigMap name changes.
- A call of the dated group that fails goes to OpenRouter again, to another provider, with the same filters. The data flow and the privacy control do not change.
- A call that the fallback serves costs at most the list price, about 4 times the price of the dated group.

## Feasibility
- The OpenRouter model list on 2026-11-13 holds `deepseek/deepseek-v4.1-flash` with a window of 1,048,576 and list prices of 0.3, 1.2 and 0.006 USD per million tokens (input, output, cached input). Its endpoint list holds more than 20 fp8 providers with status 0.
- The gateway log shows `No fallback model group found for lookup_groups=deepseek-v4.1-flash-1017` for each failed call, so LiteLLM tries a fallback when one exists.

## Existing Tool Considered
LiteLLM router fallbacks (`router_settings.fallbacks`) and OpenRouter provider routing cover the need. No new code.
