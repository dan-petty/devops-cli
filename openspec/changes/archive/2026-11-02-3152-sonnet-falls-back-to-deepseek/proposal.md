# Proposal

## Why

Issue #3152: the hosted groups of the gateway have no fallback. When Anthropic answers an error, a rate limit, or the account reaches its spend limit (this happened on 2026-11-02), a call to `claude-sonnet-5-5` fails and nothing answers. The evaluation of 2026-11-02 measured which hosted models can stand in for it.

## Feasibility

- Review of a plan, recall of the known defects of 12 golden plans (the cited files as context, no tools; an independent agent matched the findings; files under `.data/agent/scratch/model-eval/`): `claude-sonnet-5-5` 56% (68% of the major defects), `deepseek-v4.1-flash-1017` 38% (48%), `claude-haiku-5-5` 36% (46%), Gemini 3 Flash and 3.8 Flash 24 to 25%, Gemini 3.1 and 3.5 Flash Lite, Gemini 3.6 Flash and Gemma 4 7 to 14%, local `qwen3.8:27b` and `qwen3-coder:30b` 22 to 23%.
- Gemini 2.5 Flash and 2.5 Flash Lite answer HTTP 404 ("no longer available to new users"). Gemma 4 on the free tier takes 16000 input tokens a minute, below one review prompt plus its answer.
- A LiteLLM v1.103.0 `Router` built from the two groups and the fallback `claude-sonnet-5-5: [deepseek-v4.1-flash-1017]` answers a failed Sonnet call with `openrouter/deepseek/deepseek-v4.1-flash-1017:floor`. The same Router without the fallback raises `InternalServerError`.

## Existing Tool Considered

LiteLLM `router_settings.fallbacks`. No new tool.

## What Changes

- `k8s/llm/gateway/config.yaml`: the fallback `claude-sonnet-5-5: [deepseek-v4.1-flash-1017]`.
- The hosted-group check: it fails when a fallback sends a group that is not hosted to a hosted group, and still fails when a hosted group is in a context-window fallback or a routing group. One broken edit proves it.
- `k8s/README.md` and `SECURITY.md` (rule 12) say that the prompt of a failed Claude call goes to OpenRouter.
- The change modifies one requirement of `ai-gateway-routing`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-gateway-routing`: the requirement `Hosted groups join no pool` allows a fallback from a hosted group to a hosted group.

## Impact

- The gateway Deployment rolls when Argo CD syncs the ConfigMap. A failed Sonnet call is answered by DeepSeek through OpenRouter.
- The prompt of that call leaves for a second provider. The caller named a hosted group, so no prompt leaves the cluster that a caller did not send to a hosted group.
