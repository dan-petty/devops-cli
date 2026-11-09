# Proposal: #3665

## Why

An agent run on a hosted gateway group is recorded as local spend at $0 (#3665). `record_run_spend` in `src/devops_cli/roadmap/agent_run.py` writes one record per run. When no reply names a model, the record has no `served_by` and no `served_model`, and `is_local` then decides from the gateway host: a gateway that is the cluster host is local. The production counter of job `roadmap-service` on 2026-11-09 shows 68 M `claude-sonnet-5-5` prompt tokens as `local=true` at $0, while the gateway log prices them at $2 per million. The DeepSeek group shows $0 on the counter against $14 on the gateway. #3663 fixed a reply that names a model, and #4216 passes the model that a reply names. A run whose replies name no model is still wrong.

## What Changes

- `track_request_spend` in `src/devops_cli/ai/spend/ledger.py` takes the asked model as `served_model` when the provider is `gateway`, the call has no `served_by` and no `served_model`, and the asked model is a hosted group (`CONST_AI_GATEWAY_HOSTED_MODELS`). The price, the `local` label of the counters and the stored `served_model` then agree. A model that a reply names still wins. A local group keeps the local rule. `is_local` is not changed.
- `tests/ai/client/test_roadmap_agent_run.py` and `tests/ai/spend/test_ai_spend_ledger.py` hold the new tests, with the gateway host as the cluster host.
- The `ai-spend-pricing` spec gains one requirement, because the pricing source and the cost of a record are observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-spend-pricing`: adds the requirement `A hosted group is priced at the model that the client asked for`.

## Impact

- Code: `src/devops_cli/ai/spend/ledger.py`
- Tests: `tests/ai/client/test_roadmap_agent_run.py`, `tests/ai/spend/test_ai_spend_ledger.py`
- No new setting, no new constant and no new dependency. The Settings models are not changed, so no ConfigMap rollout is needed.
- The change touches neither `pydantic_ai_bridge.py` nor `stage_toolbox.py`, which #4220 changes.
- Cache tokens stay with #3658.

## Feasibility

- Checked on 2026-11-09 at origin/main 7411967a. No merged change and no open pull request does this work. #3663 fixed a reply that names a model. #4216 (merged) passes `served_model=answered[-1]` in `record_run_spend` when a reply names a model.
- `record_run_spend` (`agent_run.py`) passes `served_model=None` when no reply names a model, and passes no `served_by`. `is_local` (`ai/spend/pricing.py`) then decides from the host.
- Command output, a probe of `is_local` and `PricingRegistry.calculate_request_cost` on origin/main: with the gateway host as the cluster host, a call with provider `gateway` and no reply name is local. The same call with `served_model` set to `claude-sonnet-5-5`, `claude-haiku-5-5`, `gemini-3.8-flash` or `deepseek-v4.1-flash-1017` is not local. The prices are `genai_prices:anthropic` (above $0), `genai_prices:anthropic`, `genai_prices:google` and `unknown` ($0, with the warning that names the model and the command `devops ai cost set-price`).
- `CONST_AI_GATEWAY_HOSTED_MODELS` lists the hosted groups, and `tests/config/test_k8s_devops_runtime.py` ties it to the gateway configuration. A local group, for example `devops-coder`, is not in it.
- The eval aliases `sonnet-native` and `haiku-native` of the issue text are in no file under `src/` or `k8s/`, so no record can carry them.
- The new tests fail on origin/main with the right cause (a local record at $0): `uv run devops ci fail-to-pass --base origin/main`.
- The check after the change: `uv run devops ci test tests/ai/client/test_roadmap_agent_run.py tests/ai/spend/test_ai_spend_ledger.py`.
- Not verified here: why the counter shows 68 M local tokens against 27 M at the gateway. A double count or a fallback to another group may exist, and only the Service logs can show it. The issue comment names a test that sums the local and the hosted prompt tokens against the usage of the model. That cause is outside this change.

## Existing Tool Considered

genai-prices already prices a LiteLLM model reference, and the gateway reply header already gives the model when it is present. No library reads the asked model of a pydantic-ai run for the spend ledger, and the change adds one rule of a few lines in the one place where the asked model and the provider are both known. The header-hook design of the issue (an httpx hook that reads the reply header) was considered and rejected: see the design. The change deletes no internal code.
