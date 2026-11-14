# Proposal

## Why

A gateway call that a local group answers counts as hosted when the reply names a model outside `CONST_AI_GATEWAY_VIRTUAL_MODELS`, such as a local fallback (`ollama_chat/qwen3.8:27b`) or the group `devops-review`. The record gets the source `unknown` at 0 USD and an unpriced warning (#4886).

## What Changes

- `CONST_AI_GATEWAY_LOCAL_GROUPS` names every local group of `k8s/llm/gateway/config.yaml`.
- `_is_local_tier` accepts the local groups and the `ollama/`, `ollama_chat/` and `ollama:` prefixes.
- A test compares the constant with the gateway config and checks the classification.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-spend-pricing`: A local gateway group and an Ollama deployment name count as local.

## Impact

- Code: `src/devops_cli/config/constants.py`, `src/devops_cli/ai/spend/pricing.py`
- Tests: `tests/ai/spend/test_hosted_group_prices.py`

## Feasibility

- The gateway config lists the local deployments by their `ollama/` or `ollama_chat/` model.
- `is_local` already decides by the reply name.
- Verification commands: `uv run devops ci test tests/ai/spend` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

The pricing registry and `is_local` already exist. The change names the local groups in one constant.
