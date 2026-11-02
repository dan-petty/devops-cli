# Proposal

## Why

Issue #3144: the owner has an OpenRouter API key and wants the model `deepseek/deepseek-v4.1-flash-1017` as a gateway model, to evaluate it for the stages of the roadmap jobs and as a cheaper hosted model. The gateway has no OpenRouter key and no group for it.

## Feasibility

- OpenRouter lists `deepseek/deepseek-v4.1-flash-1017` with a window of 1048576 tokens, 393216 output tokens, 0.30 USD input and 1.20 USD output per million tokens, and the parameters `response_format`, `reasoning` and `max_completion_tokens` (`https://openrouter.ai/api/v1/models`, 2026-11-02).
- The cost map of the pinned LiteLLM image (v1.103.0) lists `openrouter/deepseek/deepseek-v4.1-flash` with the same prices and window, and no `-1017` snapshot, so the group sets its own window and prices.
- The egress rule of #3113 (TCP 443 to public addresses) already admits `openrouter.ai`.
- OpenRouter lists 40 endpoints for the model (`/api/v1/models/deepseek/deepseek-v4.1-flash-1017/endpoints`). The cheapest fp8 endpoint is 0.05 USD input and 0.192 USD output per million tokens (cache read 0.008); the owner chose that route (`:floor`, fp8). The suffix `:floor` sorts by price, and the body fields `provider.quantizations` and `provider.data_collection: deny` filter the providers. LiteLLM sends the fields with `extra_body`.
- The API does not say whether a provider stores or trains on prompts, so `data_collection: deny` can skip the cheapest fp8 provider. The README says so.

## Existing Tool Considered

LiteLLM supports the `openrouter/` provider and `os.environ/` key references. No new tool.

## What Changes

- `k8s/llm/gateway/config.yaml`: the group `deepseek-v4.1-flash-1017` (`openrouter/deepseek/deepseek-v4.1-flash-1017`), with the suffix `:floor`, fp8 weights, `data_collection: deny`, its window and the prices of the cheapest fp8 provider. No pool, fallback or routing group names it.
- `k8s/llm/gateway/deployment.yaml`: `OPENROUTER_API_KEY` from the optional key `openrouter-api-key` of `llm-gateway-secrets`.
- `src/devops_cli/k8s/cluster_secrets.py` and `src/devops_cli/config/env.py`: the optional Secret entry and the credential `openrouter.api_key`; `docs/ENV_VARS.md` lists it.
- `k8s/README.md` and `SECURITY.md` (rule 12) describe the group, the key and the data rule.
- Tests: the hosted-group check covers the group and the provider `openrouter`; the secret table, the key lists and the model count follow.
- The change modifies one requirement of `ai-gateway-routing`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-gateway-routing`: the requirement `Hosted groups call a provider with an optional key` also serves `deepseek-v4.1-flash-1017`.

## Impact

- The gateway Deployment rolls when Argo CD syncs the ConfigMap. The gateway sends a prompt to OpenRouter only when a caller names the group.
- A person stores the key and pushes it (task 2). Until then a call to the group fails with a missing-key error, and every other group works.
- Cost: OpenRouter bills each token.
