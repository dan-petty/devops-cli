# Proposal: #5853

## Why
Callers of the LLM gateway can name local models with the `local/` prefix or hosted models with cloud provider prefixes (`anthropic/`, `gemini/`, `openrouter/`). The gateway router configuration had no model aliases for these prefixes, which caused requests under prefixed names to fail. This change configures `model_group_alias` in the gateway router settings for all local model groups and provider-prefixed hosted groups. Closes #5853.

## What Changes
- Add `model_group_alias` to `router_settings` in `k8s/llm/gateway/config.yaml`.
- Map local models with `local/` prefix (`local/devops-chat`, `local/devops-coder`, `local/devops-reasoning`, `local/devops-background`, `local/devops-review`, `local/devops-triage`, `local/qwen3.8:27b`, `local/qwen3-embedding:0.6b`) to their model groups.
- Map hosted models with provider prefixes (`anthropic/claude-sonnet-5-5`, `anthropic/claude-haiku-5-5`, `gemini/gemini-3.8-flash`, `openrouter/deepseek/deepseek-v4.1-flash-1017`, `openrouter/deepseek/deepseek-v4.1-flash-1017:floor`, `openrouter/deepseek/deepseek-v4.1-flash`) to their hosted model groups.
- Add test coverage in `tests/ai/benchmark/test_k8s_llm_gateway.py` to verify alias targets exist in `model_list`.

## Capabilities
- `ai-gateway-routing`: Model routing, failover, and aliases on the LLM gateway.

## Impact
- LiteLLM gateway routes requests with `local/` and provider prefixes without duplicating deployments.
- Existing unprefixed model names continue to work unchanged.

## Feasibility
- Verified with LiteLLM Router `model_group_alias` parameter.
- Tested against full gateway configuration and model matrix test suite.

## Existing Tool Considered
LiteLLM native `model_group_alias` covers the requirement directly without extra routing proxy layers.
