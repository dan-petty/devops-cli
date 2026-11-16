# Proposal: #5988

## Why
From 2026-11-16 about 10:00Z, `openrouter/deepseek/deepseek-v4.1-flash-1017` waited about 300 s for its first token on OpenRouter, with and without `:floor` (#5978). Three probes through the gateway waited 301 to 303 s, and the job calls ended with `LLM_INFERENCE_ERROR, timeout (HTTP 504 Gateway Timeout)`: stage, refine and implement had 0 successes in 5 results from 15:10Z to 15:41Z. OpenRouter sends the timeout inside the stream as code 408, and LiteLLM (1.103.11 and 1.109.1) raises an in-stream 4xx other than 429 with no fallback, so the fallback group does not start. `openrouter/deepseek/deepseek-v4.1-flash` answers in 2 s with the same filters. Owner, 2026-11-16: run the DeepSeek jobs on it until -1017 recovers. Closes #5988.

## What Changes
- `ai.model`, each `ai.tasks` job that named -1017, and the one tier of each step class of `roadmap.implement.ladder` name `openrouter/deepseek/deepseek-v4.1-flash`.
- A template comment says when to name -1017 again: when a probe of it gives its first token in less than 10 s.

## Capabilities
- `roadmap-service-deployment`: three requirements name the new model.

## Impact
- After the merge, `devops k8s deploy-stack` applies the template. The settings reload for each round; no restart.
- The gateway prices the group `deepseek-v4.1-flash` at the DeepSeek list price (0.30 and 1.20 USD per million tokens). OpenRouter can serve it from `baidu/fp8` at 0.05 and 0.20 USD, so the spend panels can show more than the real cost until the group gets a measured price.

## Feasibility
The fp8 endpoints of `deepseek/deepseek-v4.1-flash` in the OpenRouter endpoints API have windows of 1,000,000 tokens or more, so the window 256000 of each task fits. The group `deepseek-v4.1-flash` is a hosted group of `k8s/llm/gateway/config.yaml` and is in `CONST_AI_GATEWAY_HOSTED_MODELS`. The gateway sent 564 fallback calls to it in the 7 days before.

## Existing Tool Considered
The LiteLLM fallback from the group -1017 to `deepseek-v4.1-flash` is the tool for this, but it does not start on an in-stream 408 (see Why). A setting change is the smallest step until the gateway can route around a stalled provider.
