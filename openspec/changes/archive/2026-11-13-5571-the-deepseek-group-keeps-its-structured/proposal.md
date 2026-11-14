# Proposal: #5571

## Why
PR #5565 moved the line `supports_response_schema: true` from the `model_info` of `deepseek-v4.1-flash-1017` to the new group `deepseek-v4.1-flash`: a rebase put the new group between the line and the group that owned it. The main DeepSeek group, which every chat slot of the Service names, no longer tells LiteLLM that it takes a structured reply. Closes #5571.

## What Changes
- Set `supports_response_schema: true` on `deepseek-v4.1-flash-1017` again. The fallback group keeps it too, so a call that falls back keeps its response format.
- The fallback test asserts the flag on both DeepSeek groups.

## Capabilities
- `ai-gateway-routing`: both DeepSeek groups take a structured reply.

## Impact
The gateway rolls on the Argo CD sync (the ConfigMap name holds a hash of `config.yaml`). No release.

## Feasibility
`git show 183487d72:k8s/llm/gateway/config.yaml` shows the flag under `deepseek-v4.1-flash` only. The extended test fails on `183487d72` and passes with the fix.

## Existing Tool Considered
The LiteLLM `model_info` flag already covers the need. No new code.
